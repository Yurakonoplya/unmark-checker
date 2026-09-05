"""Frozen detection thresholds. DO NOT tune these to results.

These constants decide when the detector calls a text "the mark is still there",
"in between" (the grey zone) or "our mark is gone". They were fixed before any
run of ours and are the same two numbers the hosted checker on
https://unmarkclaude.io/check reports against. Changing them after seeing a run
would invalidate every number produced with this code.

Why these values are defensible a priori, independent of model or scheme
--------------------------------------------------------------------------
The detector score is a z-statistic of the mean g-value. Under the null
hypothesis (the text carries no watermark for our key), every g-value is a fair
coin flip, Bernoulli(0.5), *regardless of which model produced the text or which
scheme parameters were picked*. So the null distribution of the z-statistic is,
to a good approximation, the standard normal N(0, 1) for ALL configurations.
That lets thresholds be fixed by the false-positive rate one is willing to
accept, before anything is known about the experiment:

    z >= Z_DETECT                -> mark_present   one-sided p <= ~3.2e-5
    Z_UNCERTAIN <= z < Z_DETECT  -> uncertain      (grey zone)
    z <  Z_UNCERTAIN             -> mark_gone      one-sided p >  ~2.3e-2

The grey zone exists because SynthID has a genuinely wide band of ambiguity: an
independent study (AIES 2026) found 8 of 10 untouched watermarked texts landing
in the uncertain band. The three outcomes are reported separately, never
collapsed into yes/no.

Note on independence: g-values across tournament layers and positions are only
approximately independent (the hash chain and context-repetition suppression
introduce mild correlation), so the empirical null spread can be slightly wider
than N(0, 1). Measure the false-positive rate on unmarked text directly
(`generate --unmarked`); if it exceeds the theoretical rate, that is a finding
to report, never a reason to move these lines.
"""

from __future__ import annotations

# One-sided z-score thresholds on the mean g-value statistic.
Z_DETECT: float = 4.0        # at/above -> the mark is still there
Z_UNCERTAIN: float = 2.0     # at/above (but below Z_DETECT) -> grey zone

# Outcome labels, identical to the ones the hosted checker and the service pages
# publish, so a local run and a run on the site can be compared word for word.
MARK_PRESENT = "mark_present"
UNCERTAIN = "uncertain"
MARK_GONE = "mark_gone"
NOT_OUR_TEXT = "not_our_text"
OUTCOMES = (MARK_PRESENT, UNCERTAIN, MARK_GONE, NOT_OUR_TEXT)


def classify(z: float) -> str:
    """Map a z-score to one of the three frozen outcomes.

    `not_our_text` is not produced here: it is decided before scoring, by asking
    whether the returned text is still recognisably the sample (see
    `identify.py`). A z-score on a text with no known starting point means
    nothing, so it is never computed.
    """
    if z >= Z_DETECT:
        return MARK_PRESENT
    if z >= Z_UNCERTAIN:
        return UNCERTAIN
    return MARK_GONE
