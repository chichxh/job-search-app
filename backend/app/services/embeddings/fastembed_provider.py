import re
from functools import lru_cache

from fastembed import TextEmbedding


DEFAULT_FASTEMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", (text or "").strip())


@lru_cache(maxsize=4)
def _load_fastembed_model(model_name: str) -> TextEmbedding:
    return TextEmbedding(model_name=model_name)


class FastEmbedEmbeddingProvider:
    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model = _load_fastembed_model(model_name)
        self._dim = len(next(self._model.embed(["dimension probe"])).tolist())

    @property
    def name(self) -> str:
        return f"fastembed:{self._model_name}"

    @property
    def dim(self) -> int:
        return self._dim

    def get_dim(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        normalized_texts = [_normalize_text(text) for text in texts]
        return [vector.astype("float32", copy=False).tolist() for vector in self._model.embed(normalized_texts)]
