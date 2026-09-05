"""Model loading, and generation with or without the mark."""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    SynthIDTextWatermarkingConfig,
    SynthIDTextWatermarkLogitsProcessor,
)

from .schemes import LengthBucket, Scheme


def build_wm_processor(scheme: Scheme, device: torch.device | str) -> SynthIDTextWatermarkLogitsProcessor:
    """The mark's logits processor, identical in every environment.

    Build it ONLY this way, both when generating and when detecting. The
    scheme's g-value table is filled by torch's RNG, and torch uses different
    RNG algorithms on CPU and CUDA for the same seed. A processor built on a GPU
    marks against a different table than one built on a CPU: a mark planted on a
    rented GPU was invisible to the local detector, and two of our pilot runs
    were scrapped before this was understood (the GPU saw its own texts at 100%,
    the local re-score at 0%). Building on CPU and moving the tensors to the
    device makes the mapping the same everywhere; moving values does not change
    them.
    """
    lp = SynthIDTextWatermarkLogitsProcessor(**scheme.kwargs(), device=torch.device("cpu"))
    dev = torch.device(device)
    if dev.type != "cpu":
        lp.sampling_table = lp.sampling_table.to(dev)
        lp.keys = lp.keys.to(dev)
        lp.device = dev
    return lp


class PortableWatermarkingConfig(SynthIDTextWatermarkingConfig):
    """A watermarking_config whose processor comes from `build_wm_processor`.

    Generation must go through `watermarking_config`, not through a custom
    `logits_processor`: the stock SynthID processor is applied AFTER temperature
    and top-k, custom ones BEFORE. A different application point changes the
    strength of the mark, that is, the object being measured (measured: z of 17
    instead of 5.7 on one and the same setup). This subclass changes only the
    table, to one shared across environments; the application point stays stock.
    """

    def __init__(self, scheme: Scheme):
        super().__init__(**scheme.kwargs())
        self._scheme = scheme

    def construct_processor(self, vocab_size: int, device) -> SynthIDTextWatermarkLogitsProcessor:
        return build_wm_processor(self._scheme, device)


@dataclass
class LM:
    """A loaded causal LM plus its tokenizer, pinned to CPU by default.

    `model` is None when only the tokenizer was loaded: scoring a text needs the
    tokenizer and the key, never the weights, and skipping the weights turns
    `check` from a minute into a second.
    """

    model_id: str
    model: object | None
    tokenizer: object
    device: torch.device

    @property
    def max_positions(self) -> int:
        cfg = self.model.config
        return int(getattr(cfg, "max_position_embeddings", None) or getattr(cfg, "n_positions", 1024) or 1024)


_DTYPES = {
    "float32": torch.float32,
    "float16": torch.float16,
    "bfloat16": torch.bfloat16,
}


def load_tokenizer(model_id: str, device: str = "cpu") -> LM:
    """Tokenizer only: everything `check` needs to score a text."""
    tok = AutoTokenizer.from_pretrained(model_id)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    return LM(model_id=model_id, model=None, tokenizer=tok, device=torch.device(device))


def load_lm(
    model_id: str,
    device: str = "cpu",
    num_threads: int | None = None,
    dtype: str = "float32",
) -> LM:
    """dtype="float16" halves GPU memory and does not touch the mark: g-values
    are computed from integer token ids, not from logits."""
    if num_threads:
        torch.set_num_threads(num_threads)
    tok = AutoTokenizer.from_pretrained(model_id)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(model_id, dtype=_DTYPES[dtype])
    model.to(device)
    model.eval()
    return LM(model_id=model_id, model=model, tokenizer=tok, device=torch.device(device))


def _bounded_max_new(lm: LM, prompt_len: int, requested: int) -> int:
    """Never ask for more tokens than the model's context can hold."""
    room = lm.max_positions - prompt_len - 4
    return max(1, min(requested, room))


@torch.no_grad()
def generate(
    lm: LM,
    prompt: str,
    bucket: LengthBucket,
    *,
    scheme: Scheme | None,
    temperature: float = 1.0,
    top_k: int = 40,
    top_p: float = 1.0,
    seed: int | None = None,
) -> str:
    """Generate one continuation. With `scheme=None` no mark is applied, which
    is how you produce a control text and see what the detector says on prose
    that never carried your mark.
    """
    if seed is not None:
        torch.manual_seed(seed)

    enc = lm.tokenizer(prompt, return_tensors="pt").to(lm.device)
    prompt_len = enc.input_ids.shape[1]
    max_new = _bounded_max_new(lm, prompt_len, bucket.max_new_tokens)
    min_new = min(bucket.min_new_tokens, max_new)

    wm_config = None
    if scheme is not None:
        wm_config = PortableWatermarkingConfig(scheme)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = lm.model.generate(
            **enc,
            do_sample=True,  # SynthID is a sampling watermark; beam/greedy applies no mark
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            max_new_tokens=max_new,
            min_new_tokens=min_new,
            watermarking_config=wm_config,
            pad_token_id=lm.tokenizer.pad_token_id,
        )
    return lm.tokenizer.decode(out[0], skip_special_tokens=True)
