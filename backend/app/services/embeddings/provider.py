import hashlib
import math
import os
from abc import ABC, abstractmethod
from functools import lru_cache


class EmbeddingProvider(ABC):
    """Базовый интерфейс провайдера эмбеддингов."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Имя провайдера/модели."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Возвращает embedding для текста."""


class LocalHashEmbeddingProvider(EmbeddingProvider):
    """Легковесный CPU-only провайдер на hashing trick без внешних ML-зависимостей."""

    def __init__(self, model_name: str, embedding_dim: int) -> None:
        self._model_name = model_name
        self._embedding_dim = embedding_dim

    @property
    def name(self) -> str:
        return f"local:{self._model_name}"

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self._embedding_dim
        tokens = (text or "").lower().split()

        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            token_hash = int.from_bytes(digest, byteorder="big", signed=False)
            idx = token_hash % self._embedding_dim
            sign = 1.0 if ((token_hash >> 1) & 1) == 0 else -1.0
            vector[idx] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector

        return [value / norm for value in vector]


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
    model_name = os.getenv("EMBEDDING_MODEL", "hashing-cpu")
    embedding_dim = int(os.getenv("EMBEDDING_DIM", "384"))

    if provider_name == "local":
        return LocalHashEmbeddingProvider(model_name=model_name, embedding_dim=embedding_dim)
    if provider_name == "openai":
        return OpenAIEmbeddingProvider()
    if provider_name == "gigachat":
        return GigaChatEmbeddingProvider()

    raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {provider_name}")
