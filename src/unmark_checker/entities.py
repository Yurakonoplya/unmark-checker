"""Formal entity check between an input text and a rewritten one.

Not a "smart" model-based check but deterministic regular expressions: they give
a provable statement about numbers, names and links surviving a rewrite.
Anything that can be checked formally is checked formally, never by a model
asked for an opinion.

Five categories are extracted, and for each one the code can say whether the
entity survived in the rewritten text. The check is deliberately strict: a false
alarm costs a second look, a missed fact costs the reader.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- Numbers -------------------------------------------------------------
# A digit run with optional thousand/decimal separators and a percent sign.
# Versions like 3.14 are captured too; the key drops thousand separators.
_NUMBER_RE = re.compile(r"\d[\d,.  ]*\d|\d")
_PERCENT_RE = re.compile(r"(\d[\d,.  ]*\d|\d)\s*%")

# --- Links ---------------------------------------------------------------
_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"')\]}]+", re.IGNORECASE)

# --- Dates ---------------------------------------------------------------
_MONTHS = {
    m.lower(): i
    for i, m in enumerate(
        [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ],
        start=1,
    )
}
_MONTH_ALT = "|".join(_MONTHS)
_DATE_MONTH_DAY = re.compile(
    rf"\b({_MONTH_ALT})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.IGNORECASE
)
_DATE_DAY_MONTH = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_ALT}),?\s+(\d{{4}})\b", re.IGNORECASE
)
_DATE_NUMERIC = re.compile(r"\b(\d{1,4})[-/.](\d{1,2})[-/.](\d{1,4})\b")

# --- Terms ---------------------------------------------------------------
# Technical tokens: acronyms (API, C2PA, SPF), mixed case (SynthID, vLLM,
# PostgreSQL) and alphanumeric identifiers (GPT-4, H100).
_TERM_ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]{1,}\b")
_TERM_MIXEDCASE = re.compile(r"\b[A-Za-z]+[A-Z][A-Za-z0-9]*\b")
_TERM_ALNUM = re.compile(r"\b(?=[A-Za-z]*\d)(?=\d*[A-Za-z])[A-Za-z]+[A-Za-z0-9.\-]*\b")

# --- Proper names --------------------------------------------------------
_CAP_TOKEN = re.compile(r"[A-Z][a-zA-Z'’.&\-]*[a-zA-Z]|[A-Z]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_NAME_CONNECTORS = {"of", "the", "and", "for", "de", "van", "von", "der", "la", "le"}
# Frequent words that are capitalised without being a name (sentence start).
_COMMON_CAP_WORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "this", "that", "these",
    "those", "it", "its", "they", "them", "their", "there", "here", "we", "our",
    "you", "your", "he", "she", "his", "her", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "as", "is", "are", "was", "were", "be", "been", "being",
    "so", "no", "not", "yes", "when", "where", "while", "because", "since", "after",
    "before", "however", "meanwhile", "instead", "also", "still", "yet", "both",
    "each", "every", "some", "any", "many", "much", "more", "most", "such", "only",
    "even", "just", "now", "later", "today", "tomorrow", "yesterday", "one", "two",
    "three", "first", "second", "third", "next", "last", "another", "other",
}


@dataclass
class Entity:
    text: str  # as it appeared in the source, for the report
    key: str  # normalised key used for matching


@dataclass
class EntitySet:
    numbers: list[Entity] = field(default_factory=list)
    dates: list[Entity] = field(default_factory=list)
    urls: list[Entity] = field(default_factory=list)
    names: list[Entity] = field(default_factory=list)
    terms: list[Entity] = field(default_factory=list)

    def categories(self) -> dict[str, list[Entity]]:
        return {
            "numbers": self.numbers,
            "dates": self.dates,
            "urls": self.urls,
            "names": self.names,
            "terms": self.terms,
        }

    def total(self) -> int:
        return sum(len(v) for v in self.categories().values())


def _norm_number(raw: str) -> str:
    """Drop thousand separators and stray spaces, keep the fractional part."""
    s = raw.replace(" ", "").replace(" ", "").replace(",", "")
    return s.strip(".")


def _dedup(entities: list[Entity]) -> list[Entity]:
    seen: set[str] = set()
    out: list[Entity] = []
    for e in entities:
        if e.key in seen:
            continue
        seen.add(e.key)
        out.append(e)
    return out


def _extract_numbers(text: str) -> list[Entity]:
    out: list[Entity] = []
    pct_spans: set[tuple[int, int]] = set()
    for m in _PERCENT_RE.finditer(text):
        key = _norm_number(m.group(1)) + "%"
        out.append(Entity(text=m.group(0).strip(), key=key))
        pct_spans.add(m.span(1))
    for m in _NUMBER_RE.finditer(text):
        if m.span() in pct_spans:
            continue
        key = _norm_number(m.group(0))
        if not any(c.isdigit() for c in key):
            continue
        out.append(Entity(text=m.group(0), key=key))
    return _dedup(out)


def _canon_date(y: str, mon: int, d: str) -> str:
    return f"{int(y):04d}-{mon:02d}-{int(d):02d}"


def _extract_dates(text: str) -> list[Entity]:
    out: list[Entity] = []
    for m in _DATE_MONTH_DAY.finditer(text):
        mon = _MONTHS[m.group(1).lower()]
        out.append(Entity(text=m.group(0), key=_canon_date(m.group(3), mon, m.group(2))))
    for m in _DATE_DAY_MONTH.finditer(text):
        mon = _MONTHS[m.group(2).lower()]
        out.append(Entity(text=m.group(0), key=_canon_date(m.group(3), mon, m.group(1))))
    for m in _DATE_NUMERIC.finditer(text):
        # Component order is ambiguous, so the key is the sorted set of numbers.
        parts = sorted(int(x) for x in m.groups())
        out.append(Entity(text=m.group(0), key="d:" + "-".join(str(p) for p in parts)))
    return _dedup(out)


def _extract_urls(text: str) -> list[Entity]:
    out: list[Entity] = []
    for m in _URL_RE.finditer(text):
        raw = m.group(0).rstrip(".,;:!?)")
        out.append(Entity(text=raw, key=raw.lower()))
    return _dedup(out)


def _extract_terms(text: str) -> list[Entity]:
    out: list[Entity] = []
    for rex in (_TERM_ACRONYM, _TERM_MIXEDCASE, _TERM_ALNUM):
        for m in rex.finditer(text):
            tok = m.group(0)
            if tok.isdigit():
                continue
            out.append(Entity(text=tok, key=tok.lower()))
    return _dedup(out)


def _mask_spans(text: str, patterns) -> str:
    """Replace already recognised links, dates, numbers and terms with a control
    character of the same length, so name extraction does not shatter them into
    fragments ('Qwen', 'C', 'PA').

    A control character rather than a space, deliberately: a whitespace mask
    glued names ACROSS the masked hole ('Hancock <mask> Habit Brew'). Such a
    phrase exists in the masked text but not in the source, so the check could
    not find it even in an untouched text and an honest output was scored as
    having lost an entity. A non-space mask breaks the glue: gap.strip() is
    non-empty and is not a connector, so a name does not continue through it.
    """
    chars = list(text)
    for rex in patterns:
        for m in rex.finditer(text):
            for k in range(m.start(), m.end()):
                chars[k] = "\x00"
    return "".join(chars)


def _extract_names(text: str) -> list[Entity]:
    masked = _mask_spans(
        text,
        (_URL_RE, _DATE_MONTH_DAY, _DATE_DAY_MONTH, _DATE_NUMERIC,
         _TERM_ACRONYM, _TERM_MIXEDCASE, _TERM_ALNUM, _PERCENT_RE, _NUMBER_RE),
    )
    out: list[Entity] = []
    for sentence in _SENTENCE_SPLIT.split(masked):
        tokens = list(_CAP_TOKEN.finditer(sentence))
        i = 0
        while i < len(tokens):
            run = [tokens[i]]
            j = i + 1
            while j < len(tokens):
                gap = sentence[tokens[j - 1].end():tokens[j].start()]
                connector = gap.strip().lower()
                # A name never continues across a line break: a heading and the
                # first line of the next block ("Santa Cruz\n\nImage Credit") are
                # not one name. No segment protects such a splice (the paragraph
                # boundary runs between them), and a whole-document check scored
                # it as lost while every fact was intact.
                if "\n" in gap:
                    break
                if gap.strip() == "" or connector in _NAME_CONNECTORS:
                    run.append(tokens[j])
                    j += 1
                else:
                    break
            toks = [sentence[t.start():t.end()] for t in run]
            # Trim common words at the edges (sentence start, dangling connector)
            # but take the ORIGINAL substring between the outermost tokens: inner
            # connectors ('of', 'and') survive and the key exists in the text.
            lo, hi = 0, len(toks)
            while lo < hi and toks[lo].lower() in _COMMON_CAP_WORDS:
                lo += 1
            while hi > lo and toks[hi - 1].lower() in (_COMMON_CAP_WORDS | _NAME_CONNECTORS):
                hi -= 1
            if hi <= lo:
                i = j
                continue
            phrase = sentence[run[lo].start():run[hi - 1].end()].strip()
            n_words = hi - lo
            # A single fragment (one letter) or a common word is not a name.
            if not phrase or (n_words == 1 and len(phrase) < 2):
                i = j
                continue
            if n_words == 1 and phrase.lower() in _COMMON_CAP_WORDS:
                i = j
                continue
            if any(c.isalpha() for c in phrase):
                out.append(Entity(text=phrase, key=phrase.lower()))
            i = j
    return _dedup(out)


def extract_entities(text: str) -> EntitySet:
    return EntitySet(
        numbers=_extract_numbers(text),
        dates=_extract_dates(text),
        urls=_extract_urls(text),
        names=_extract_names(text),
        terms=_extract_terms(text),
    )


# --- Survival check in the output ----------------------------------------


def _present_wordish(key: str, haystack_lower: str) -> bool:
    """Presence with word boundaries, so 'Ana' does not match inside 'Banana'."""
    pat = r"(?<![A-Za-z0-9])" + re.escape(key) + r"(?![A-Za-z0-9])"
    return re.search(pat, haystack_lower) is not None


@dataclass
class CategoryCheck:
    expected: list[str]
    missing: list[str]

    @property
    def preserved(self) -> int:
        return len(self.expected) - len(self.missing)

    def to_dict(self) -> dict:
        return {
            "expected": self.expected,
            "missing": self.missing,
            "preserved": self.preserved,
            "lost": len(self.missing),
        }


@dataclass
class EntityCheck:
    categories: dict[str, CategoryCheck]

    @property
    def all_present(self) -> bool:
        return all(not c.missing for c in self.categories.values())

    @property
    def total_missing(self) -> int:
        return sum(len(c.missing) for c in self.categories.values())

    def missing_flat(self) -> list[str]:
        out: list[str] = []
        for c in self.categories.values():
            out.extend(c.missing)
        return out

    def to_dict(self) -> dict:
        return {name: c.to_dict() for name, c in self.categories.items()}


def check_presence(expected: EntitySet, output_text: str) -> EntityCheck:
    out_lower = output_text.lower()
    out_numbers = {e.key for e in _extract_numbers(output_text)}
    out_dates = {e.key for e in _extract_dates(output_text)}

    result: dict[str, CategoryCheck] = {}
    for name, items in expected.categories().items():
        missing: list[str] = []
        for e in items:
            if name == "numbers":
                ok = e.key in out_numbers
            elif name == "dates":
                ok = e.key in out_dates
            elif name == "urls":
                ok = e.key in out_lower
            else:  # names, terms
                ok = _present_wordish(e.key, out_lower)
            if not ok:
                missing.append(e.text)
        result[name] = CategoryCheck(expected=[e.text for e in items], missing=missing)
    return EntityCheck(categories=result)
