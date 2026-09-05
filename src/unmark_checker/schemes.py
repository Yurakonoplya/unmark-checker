"""Scheme configurations, length buckets and generation prompts.

The watermark used here is a SynthID-Text class scheme (the class published by
DeepMind in Nature, 2024, and shipped in Hugging Face `transformers`), applied
to an OPEN-WEIGHTS model with YOUR OWN secret key. No vendor's key is involved
and no claim is made about any vendor's text: what is measured is how a mark of
this class behaves when a tool rewrites the text around it.

Three axes are varied, the same three the methodology names:

  - ngram_len           : how long a context window the hash reads
  - keys (len == depth) : how many tournament layers the scheme runs
  - context_history_size: how far back repeated-context suppression looks

**The keys are yours and are never stored in this repository.** They are derived
from the secret you pass on the command line (or in `UNMARK_CHECKER_KEY`), so
the same secret always reproduces the same scheme and a different secret gives a
different, unrelated mark. Generate with your secret, hand the sample to a
service, check the returned text with the same secret. Nobody else can score
your samples, which is the whole point: a service cannot tune its output to a
key it does not have.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

# Keys are 16-bit hash keys of the scheme; this is the range the reference
# implementation uses.
_KEY_MODULUS = 65535


@dataclass(frozen=True)
class Scheme:
    """One SynthID-Text configuration.

    Field names match `transformers.SynthIDTextWatermarkingConfig`, so the dict
    goes straight into both the watermarking config and the detector's logits
    processor. The detector MUST be built with identical values, or it scores a
    different pseudo-random sequence and sees nothing.
    """

    name: str
    ngram_len: int
    keys: list[int]
    context_history_size: int = 1024
    sampling_table_size: int = 2 ** 16
    sampling_table_seed: int = 0

    @property
    def depth(self) -> int:
        return len(self.keys)

    def kwargs(self) -> dict:
        return {
            "ngram_len": self.ngram_len,
            "keys": list(self.keys),
            "context_history_size": self.context_history_size,
            "sampling_table_size": self.sampling_table_size,
            "sampling_table_seed": self.sampling_table_seed,
        }


@dataclass(frozen=True)
class SchemePreset:
    """A named point on the scheme grid, with the key list left empty.

    A preset is public: it says how deep the context window and the tournament
    are. The keys that turn a preset into a usable scheme come from your secret
    and only from there.
    """

    name: str
    ngram_len: int
    depth: int
    context_history_size: int

    def with_secret(self, secret: str) -> Scheme:
        return Scheme(
            name=self.name,
            ngram_len=self.ngram_len,
            keys=derive_keys(secret, self.depth, self.name),
            context_history_size=self.context_history_size,
        )


def derive_keys(secret: str, depth: int, scheme_name: str = "") -> list[int]:
    """Turn a human-typed secret into the scheme's key list, deterministically.

    SHA-256 over the secret, the scheme name and a counter. Two properties
    matter and both are cheap: the same secret always yields the same keys (so a
    sample generated last week is still scoreable today), and keys of different
    presets do not overlap (so a sample marked with `shallow` does not score on
    `deep` by accident).
    """
    if not secret:
        raise ValueError("empty secret: pass --key or set UNMARK_CHECKER_KEY")
    seed = hashlib.sha256(f"{scheme_name}\x00{secret}".encode("utf-8")).digest()
    out: list[int] = []
    seen: set[int] = set()
    counter = 0
    while len(out) < depth:
        block = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        for i in range(0, len(block), 2):
            value = int.from_bytes(block[i:i + 2], "big") % _KEY_MODULUS + 1
            if value in seen:
                continue
            seen.add(value)
            out.append(value)
            if len(out) == depth:
                break
        counter += 1
    return out


def key_fingerprint(secret: str) -> str:
    """Short public tag of a secret: lets a manifest say "same key" without
    holding the key. Not reversible, and not enough to score anything."""
    return hashlib.sha256(f"unmark-checker\x00{secret}".encode("utf-8")).hexdigest()[:12]


# Three configurations spanning shallow/short to deep/long context. Running all
# three is what lets a conclusion read "across all tested configurations"
# instead of "at the one point we picked".
PRESETS: dict[str, SchemePreset] = {
    "shallow": SchemePreset("shallow", ngram_len=2, depth=10, context_history_size=256),
    "default": SchemePreset("default", ngram_len=5, depth=20, context_history_size=1024),
    "deep": SchemePreset("deep", ngram_len=8, depth=30, context_history_size=1024),
}
DEFAULT_SCHEME = "default"


def build_scheme(name: str, secret: str) -> Scheme:
    if name not in PRESETS:
        known = ", ".join(PRESETS)
        raise ValueError(f"unknown scheme {name!r}; known schemes: {known}")
    return PRESETS[name].with_secret(secret)


@dataclass(frozen=True)
class LengthBucket:
    name: str
    target_words: int

    @property
    def max_new_tokens(self) -> int:
        # ~1.4 tokens per English word for GPT/Qwen tokenizers, plus headroom.
        return int(self.target_words * 1.6) + 16

    @property
    def min_new_tokens(self) -> int:
        return int(self.target_words * 1.1)


# Neutral, varied prompts. For a base (non-instruct) model these are prefixes to
# continue; for an instruct model they read as short tasks. The content is
# deliberately generic: what is measured is the mark, not the topic.
PROMPTS: tuple[str, ...] = (
    "The history of long-distance trade is",
    "One thing every gardener eventually learns is",
    "When people first started keeping written records, they",
    "The most surprising fact about the deep ocean is",
    "A short guide to reading an old map begins with",
    "Over the last century, the way cities are lit at night",
    "The difference between weather and climate comes down to",
    "In the early days of railways, passengers were",
    "To understand why bread rises, it helps to",
    "The invention of the printing press changed",
    "Among the oldest musical instruments ever found are",
    "The reason honey never really spoils is",
    "Before clocks were common, towns kept time by",
    "The first attempts to map the human body were",
    "What makes a good bridge stand for centuries is",
    "The story of how tea reached Europe involves",
)
