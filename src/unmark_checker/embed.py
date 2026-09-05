"""Meaning similarity through a small open embedding model.

Computed with transformers directly (AutoModel plus mean pooling) rather than
through sentence-transformers: fewer dependencies, same result, the cosine
between mean-pooled and normalised embeddings. The model is small (MiniLM class)
and runs on CPU.
"""

from __future__ import annotations

import threading


class Embedder:
    def __init__(self, model_name: str):
        import torch
        from transformers import AutoModel, AutoTokenizer

        self._torch = torch
        self.name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.eval()
        # The model is not built for concurrent calls. Scoring on CPU happens one
        # after another anyway, so the lock costs nothing.
        self._lock = threading.Lock()

    def _embed_batch(self, texts: list[str]):
        torch = self._torch
        enc = self.tokenizer(
            texts, return_tensors="pt", truncation=True, max_length=512, padding=True
        )
        with torch.no_grad():
            out = self.model(**enc)
        # Mean pooling over tokens, weighted by the attention mask.
        hidden = out.last_hidden_state
        mask = enc["attention_mask"].unsqueeze(-1).float()
        summed = (hidden * mask).sum(dim=1)
        counts = mask.sum(dim=1).clamp(min=1e-9)
        mean = summed / counts
        return torch.nn.functional.normalize(mean, p=2, dim=1)

    def _embed(self, text: str):
        return self._embed_batch([text])

    def similarity(self, a: str, b: str) -> float:
        if not a.strip() or not b.strip():
            return 0.0
        with self._lock:
            va = self._embed(a)
            vb = self._embed(b)
            return float((va * vb).sum().item())

    def vectors(self, texts: list[str], batch: int = 16) -> list[list[float]]:
        """Normalised vectors for several chunks in one pass.

        Needed where two sets of chunks are compared rather than two texts (see
        kpi.py): pairwise similarity() calls would embed the same chunk once per
        chunk on the other side and turn a second of work into a minute. The
        vectors are normalised, so the cosine between them is a plain dot
        product and needs no torch.
        """
        out: list[list[float]] = []
        with self._lock:
            for start in range(0, len(texts), batch):
                # An empty chunk is accepted by the tokenizer but its attention
                # mask is all zeros: substitute a space to avoid dividing by zero.
                part = [t if t.strip() else " " for t in texts[start: start + batch]]
                out.extend(self._embed_batch(part).tolist())
        return out
