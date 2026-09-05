"""Key-aware mean g-value detector.

This is the non-learned SynthID-Text detector: it needs no trained model, only
the secret key. It reproduces exactly the masking that
`transformers.SynthIDTextWatermarkDetector` uses (context-repetition mask * eos
mask, skipping the first ngram_len-1 tokens) and then, instead of the Bayesian
head, computes the mean g-value and its z-score under the null.

Why the mean g-value and not the Bayesian detector: the Bayesian head shipped in
transformers requires a BayesianDetectorModel trained on watermarked and plain
examples. The mean g-value score is the standard key-only baseline from the
SynthID paper and gives a numeric confidence directly. It is also the honest
"knows the key" detector the methodology calls for, and the strongest position
anyone can be in with respect to a text: strictly stronger than any third-party
detector that does not hold the key.

Score:
    g-values g_i in {0,1}; with no watermark, E[g_i] = 0.5, Var = 0.25.
    z = (mean_g - 0.5) / (0.5 / sqrt(n_eff))
where n_eff = (valid positions) * depth. Larger z means stronger evidence of the
mark. Thresholds live in thresholds.py and are frozen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import torch

from . import thresholds
from .schemes import Scheme
from .watermark import LM, build_wm_processor


@dataclass
class Detection:
    z: float
    mean_g: float
    n_eff: int
    p_value: float          # one-sided, under the N(0,1) null
    outcome: str            # one of thresholds.OUTCOMES
    n_words: int


def _normal_sf(z: float) -> float:
    """One-sided upper-tail probability of the standard normal."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


class KeyAwareDetector:
    """Builds a logits processor for the scheme's key and scores token ids."""

    def __init__(self, lm: LM, scheme: Scheme):
        self.lm = lm
        self.scheme = scheme
        self.eos_id = lm.tokenizer.eos_token_id
        # The g-value table is built on CPU and moved: generation and detection
        # must share one table in every environment (see build_wm_processor).
        self.lp = build_wm_processor(scheme, lm.device)

    @torch.no_grad()
    def score_ids(self, token_ids: torch.Tensor, n_words: int = 0) -> Detection:
        ids = token_ids.to(self.lm.device)
        if ids.dim() == 1:
            ids = ids.unsqueeze(0)
        n = self.lp.ngram_len

        # Same masking as transformers.SynthIDTextWatermarkDetector.__call__.
        eos_mask = self.lp.compute_eos_token_mask(input_ids=ids, eos_token_id=self.eos_id)[:, n - 1:]
        rep_mask = self.lp.compute_context_repetition_mask(input_ids=ids)
        combined = (rep_mask * eos_mask).float()            # (B, L-(n-1))
        g_values = self.lp.compute_g_values(input_ids=ids).float()  # (B, L-(n-1), depth)

        mask = combined.unsqueeze(-1).expand_as(g_values)
        n_eff = float(mask.sum().item())
        if n_eff < 1.0:
            return Detection(z=0.0, mean_g=0.5, n_eff=0, p_value=1.0,
                             outcome=thresholds.MARK_GONE, n_words=n_words)

        mean_g = float((g_values * mask).sum().item() / n_eff)
        z = (mean_g - 0.5) / (0.5 / math.sqrt(n_eff))
        return Detection(
            z=z,
            mean_g=mean_g,
            n_eff=int(n_eff),
            p_value=_normal_sf(z),
            outcome=thresholds.classify(z),
            n_words=n_words,
        )

    def score_text(self, text: str) -> Detection:
        """Score a text the way every group is scored: text -> tokenizer -> detector.

        `add_special_tokens=False` is mandatory, not cosmetic. Some tokenizers
        (OPT, for one) prepend a BOS token equal to eos, and the detector's eos
        mask then zeroes every position: any text scores exactly z = 0.0. A flat
        zero on every text is the signature of this bug, not of a weak mark.
        """
        ids = self.lm.tokenizer(text, return_tensors="pt", add_special_tokens=False).input_ids
        return self.score_ids(ids, n_words=len(text.split()))
