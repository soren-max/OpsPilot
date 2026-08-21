import hashlib
import math
import re


def tokenize(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9_-]+", text.lower()))


class DeterministicHashEmbedding:
    """Offline test/demo embedding; stable and intentionally not a semantic production model."""

    provider_name = "opspilot"
    model_name = "deterministic-hash"
    version = "1"

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple(self._one(text) for text in texts)

    def _one(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += -1.0 if digest[4] & 1 else 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return tuple(value / norm for value in vector)


def sparse_vector(text: str) -> tuple[tuple[int, ...], tuple[float, ...]]:
    counts: dict[int, float] = {}
    for token in tokenize(text):
        index = int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big")
        counts[index] = counts.get(index, 0.0) + 1.0
    indices = tuple(sorted(counts))
    return indices, tuple(counts[index] for index in indices)
