"""Control texts: unmarked model output, or human prose.

A control text is text that never carried your mark. Scoring it tells you how
often the detector fires on nothing, which is the baseline every "the mark is
gone" claim is read against. Without it, "not detected" is a number with no
scale.
"""

from __future__ import annotations

from pathlib import Path

from .schemes import PROMPTS, LengthBucket

DATA_DIR = Path(__file__).resolve().parent / "data"
HUMAN_CORPUS = DATA_DIR / "human_corpus.txt"


def unmarked_model_texts(lm, bucket: LengthBucket, n: int, seed0: int = 0) -> list[str]:
    """N continuations from the same model with NO watermark: the strict null."""
    from .watermark import generate  # imported here: human_texts needs no torch

    out = []
    for i in range(n):
        prompt = PROMPTS[i % len(PROMPTS)]
        out.append(generate(lm, prompt, bucket, scheme=None, seed=seed0 + i))
    return out


def human_texts(bucket: LengthBucket, n: int) -> list[str]:
    """N chunks of ~target_words words of bundled human-written prose.

    Never routed through any model: this is the other end of the control, prose
    a model never touched.
    """
    if not HUMAN_CORPUS.exists():
        raise FileNotFoundError(f"human corpus not found at {HUMAN_CORPUS}")
    words = HUMAN_CORPUS.read_text(encoding="utf-8").split()
    win = bucket.target_words
    chunks: list[str] = []
    step = max(1, win // 2)  # overlap, so a short corpus still yields n windows
    i = 0
    while len(chunks) < n and i + 1 < len(words):
        chunks.append(" ".join(words[i:i + win]))
        i += step
        if i >= len(words):
            i = 0  # wrap: corpus smaller than n*win
    return chunks[:n]
