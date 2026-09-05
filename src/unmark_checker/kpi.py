"""Check metrics: what a tool did to your sample.

One set of numbers measures everything the same way: another company's tool, our
own pipeline, and a text you paste into the hosted checker. There is exactly one
implementation of these metrics, in this file; a second one would drift and the
comparison would quietly stop being a comparison.

The module depends on `embed.py`, `entities.py` and the standard library, and on
nothing else. That is deliberate: it is the same file the hosted service runs, so
it can carry no import from any service of ours.

What is measured here, and why in this shape:

* **The mark** arrives as a number from outside (`z`) together with its outcome:
  the thresholds are frozen (see thresholds.py) and are not re-decided here.
* **Meaning** (`similarity`) is computed chunk by chunk, not over the whole text.
  The reason is practical: an embedding model sees no further than its window, so
  on a thousand words a whole-text comparison silently becomes a comparison of
  first paragraphs. Both texts are cut into chunks of at most 120 words, and each
  chunk of the sample is matched to its closest chunk of the result. This also
  makes the metric indifferent to paragraph reordering: a tool that only shuffled
  blocks lost no meaning, and the number says so honestly.
* **Facts** (`facts_*`) use the same deterministic check as the product report
  (`entities.py`): numbers, dates, links, names and terms.
* **Verbatim** (`verbatim_longest_run`) and **changed share** (`changed_share`)
  answer whether any work happened at all: a tool that returned the text nearly
  untouched cannot have removed a mark, whatever it calls itself.
* **Length** (`length_ratio`) catches the most common way to cheat: compress the
  text threefold and report "no mark", because there is nothing left to measure.

All metrics share one unit: a word is what `WORD_RE` finds. Numbers are not
rounded here; rounding belongs to display, not to storage.
"""

from __future__ import annotations

import difflib
import hashlib
import math
import os
import re

from .embed import Embedder
from .entities import check_presence, extract_entities

# Version of the metric set. It changes on any change of the computation: runs
# are only comparable within one version.
KPI_VERSION = 1

# A word. The same definition the hosted checker uses: latin letters, lowercased;
# punctuation and digits do not count.
WORD_RE = re.compile(r"[a-z]+")

# Chunk size for meaning similarity. 120 words is well below the model's window
# (512 tokens), so a chunk fits its view whole and is never truncated.
CHUNK_WORDS = 120

# How many missing facts to list. The list is for understanding, not for
# completeness: a tool that lost two hundred numbers is explained by the first
# twenty.
MAX_MISSING = 20

# The embedding model. All runs must use one model or they are not comparable;
# the environment variable exists so a fork can pin its own without a code change.
EMBED_MODEL = os.environ.get("UNMARK_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

_PARA_RE = re.compile(r"\n\s*\n")
_SENT_RE = re.compile(r"(?<=[.!?])\s+")

_embedder: Embedder | None = None

# Vectors of texts already embedded. The sample side of a check is one of a few
# dozen fixed texts, so recomputing it for every reader would double the wait for
# nothing. The cache key is a hash of the text, not its id: this module knows
# nothing about any sample pool or service.
_VECTOR_CACHE_SIZE = 64
_vector_cache: dict[str, list[list[float]]] = {}


def get_embedder() -> Embedder:
    """One embedding model per process: loading it costs seconds."""
    global _embedder
    if _embedder is None:
        _embedder = Embedder(EMBED_MODEL)
    return _embedder


def _cached_vectors(model, pieces: list[str], text: str) -> list[list[float]]:
    key = hashlib.sha1(text.encode("utf-8")).hexdigest()
    hit = _vector_cache.get(key)
    if hit is not None:
        return hit
    value = model.vectors(pieces)
    if len(_vector_cache) >= _VECTOR_CACHE_SIZE:
        _vector_cache.pop(next(iter(_vector_cache)))
    _vector_cache[key] = value
    return value


def words(text: str) -> list[str]:
    """The words of a text in order: the unit of every metric here."""
    return WORD_RE.findall(text.lower())


def chunks(text: str, limit: int = CHUNK_WORDS) -> list[str]:
    """Chunks of at most `limit` words, split on paragraph and sentence bounds.

    The boundaries are chosen so a chunk stays a meaningful passage: a cut in the
    middle of a phrase would be compared by the model against anything. A
    paragraph longer than the limit is split by sentences; a sentence longer than
    the limit (it happens with tools that return text without punctuation) is
    split by words, otherwise it would run into the tokenizer's truncation
    silently.
    """
    out: list[str] = []
    for para in _PARA_RE.split(text):
        para = para.strip()
        if not para:
            continue
        if len(words(para)) <= limit:
            out.append(para)
            continue
        buf: list[str] = []
        used = 0
        for sentence in _SENT_RE.split(para):
            sentence = sentence.strip()
            count = len(words(sentence))
            if not count:
                continue
            if buf and used + count > limit:
                out.append(" ".join(buf))
                buf, used = [], 0
            if count > limit:
                tokens = sentence.split()
                for i in range(0, len(tokens), limit):
                    out.append(" ".join(tokens[i : i + limit]))
                continue
            buf.append(sentence)
            used += count
        if buf:
            out.append(" ".join(buf))
    return out


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def semantic_similarity(sample_text: str, returned_text: str, embedder=None) -> float:
    """Mean similarity of each sample chunk to its closest result chunk, 0..1.

    The direction matters: the question is "did every chunk of the sample
    survive", not the reverse. A tool that added three paragraphs of its own lost
    no meaning; a tool that dropped half the text did, and the number sees it.
    """
    left = chunks(sample_text)
    right = chunks(returned_text)
    if not left or not right:
        return 0.0
    model = embedder or get_embedder()
    va = _cached_vectors(model, left, sample_text)
    vb = model.vectors(right)
    total = 0.0
    for vec in va:
        total += max(_cosine(vec, other) for other in vb)
    value = total / len(va)
    # A cosine can be negative, this metric cannot: 0 means "nothing in common".
    return min(1.0, max(0.0, value))


def verbatim_longest_run(sample_words: list[str], returned_words: list[str]) -> int:
    """The longest verbatim surviving run, in words."""
    if not sample_words or not returned_words:
        return 0
    matcher = difflib.SequenceMatcher(None, sample_words, returned_words, autojunk=False)
    return int(matcher.find_longest_match(0, len(sample_words), 0, len(returned_words)).size)


def changed_share(sample_words: list[str], returned_words: list[str]) -> float:
    """Share of sample words that fell into no matching block, 0..1."""
    if not sample_words:
        return 0.0
    matcher = difflib.SequenceMatcher(None, sample_words, returned_words, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return max(0.0, min(1.0, 1.0 - matched / len(sample_words)))


def facts(sample_text: str, returned_text: str) -> dict:
    """Numbers, dates, links, names and terms, by the same deterministic check."""
    expected = extract_entities(sample_text)
    result = check_presence(expected, returned_text)
    total = expected.total()
    missing = result.missing_flat()
    return {
        "facts_total": total,
        "facts_preserved": total - len(missing),
        "facts_missing": missing[:MAX_MISSING],
    }


def compute(
    sample_text: str,
    returned_text: str,
    z: float | None,
    outcome: str,
    embedder=None,
) -> dict:
    """The full metric set, version `KPI_VERSION`.

    `z` and `outcome` come from outside: they are produced by the detector that
    knows the sample's key (see detector.py), against the frozen thresholds. They
    are placed into the set here so that a reader and a published page receive one
    whole object rather than two pieces someone glues together later.
    """
    sample_words = words(sample_text)
    returned_words = words(returned_text)
    out = {
        "z": None if z is None else float(z),
        "outcome": outcome,
        "similarity": semantic_similarity(sample_text, returned_text, embedder),
        **facts(sample_text, returned_text),
        "verbatim_longest_run": verbatim_longest_run(sample_words, returned_words),
        "changed_share": changed_share(sample_words, returned_words),
        "length_ratio": (len(returned_words) / len(sample_words)) if sample_words else 0.0,
        "kpi_version": KPI_VERSION,
    }
    for key in ("similarity", "changed_share", "length_ratio"):
        if not math.isfinite(out[key]):
            out[key] = 0.0
    return out
