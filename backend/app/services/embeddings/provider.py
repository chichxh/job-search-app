import os
from abc import ABC, abstractmethod
from functools import lru_cache

from sentence_transformers import SentenceTransformer


class EmbeddingProvider(ABC):
    """Базовый интерфейс провайдера эмбеддингов."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Имя провайдера/модели."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Возвращает embedding для текста."""


class LocalSentenceTransformerProvider(EmbeddingProvider):
    """Локальный провайдер на sentence-transformers."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model = SentenceTransformer(model_name)

    @property
    def name(self) -> str:
        return f"local:{self._model_name}"

    def embed_text(self, text: str) -> list[float]:
        vector = self._model.encode(text or "", normalize_embeddings=True)
        return vector.tolist()


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Заглушка для будущей интеграции OpenAI."""

    @property
    def name(self) -> str:
        return "openai:TODO"

    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError("TODO: реализовать OpenAI провайдер")


class GigaChatEmbeddingProvider(EmbeddingProvider):
    """Заглушка для будущей интеграции GigaChat."""

    @property
    def name(self) -> str:
        return "gigachat:TODO"

    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError("TODO: реализовать GigaChat провайдер")


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    """Фабрика провайдера из env."""

    provider_name = os.getenv("EMBEDDING_PROVIDER", "local").lower()
    model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    if provider_name == "local":
        return LocalSentenceTransformerProvider(model_name=model_name)
    if provider_name == "openai":
        return OpenAIEmbeddingProvider()
    if provider_name == "gigachat":
        return GigaChatEmbeddingProvider()

    raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {provider_name}")
