"""Is the returned text still the sample we started from?

A detector score on a text that has no known starting point means nothing: the
number would be a statement about someone else's material, not about what a tool
did to a sample. So before anything is scored, the returned text is compared to
the sample by content-word overlap, and a text that fails the comparison gets its
own outcome, `not_our_text`, with no metrics attached.

The rule and the 0.5 threshold are the same ones the hosted checker at
https://unmarkclaude.io/check applies, so a local run and a run on the site
answer the same way on the same pair of texts.
"""

from __future__ import annotations

import re

# Words a text is recognised by: no function words, nothing shorter than four
# letters. Two unrelated English texts share plenty of "the" and "with"; they do
# not share content words.
STOPWORDS = frozenset(
    """the of and to a in that is it for was with as on are be this by not but have
    from at or he she they we you i his her their our its an if then than so such
    been being had has do does did will would can could may might shall should must
    about into over under after before while when where which who whom what how why
    all any both each few more most other some only own same too very just also
    there here""".split()
)
WORD_RE = re.compile(r"[a-z]+")

# Below this share of the returned text's content words coming from the sample,
# the pair is not a sample and its result.
SIMILARITY_MIN = 0.5


def content_words(text: str) -> set[str]:
    """The words a text is recognised by: no stop words, four letters or more."""
    return {w for w in WORD_RE.findall(text.lower()) if len(w) >= 4 and w not in STOPWORDS}


def overlap(returned: str, sample: str) -> float:
    """Share of the returned text's content words that come from the sample, 0..1.

    Asymmetric on purpose: a tool is allowed to shorten or expand, but whatever
    it returns has to be made of the sample's material.
    """
    words = content_words(returned)
    if not words:
        return 0.0
    return len(words & content_words(sample)) / len(words)


def is_same_text(returned: str, sample: str) -> bool:
    return overlap(returned, sample) >= SIMILARITY_MIN
