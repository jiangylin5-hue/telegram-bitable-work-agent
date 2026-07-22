from __future__ import annotations

import hashlib
import struct
from typing import Protocol


TEST_EMBEDDING_PROFILE = "stage08.test-hash-v1"
TEST_EMBEDDING_VERSION = 1
TEST_EMBEDDING_DIMENSION = 8


class EmbeddingProvider(Protocol):
    profile: str
    version: int
    dimension: int

    def embed_batch(
        self,
        profile: str,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]: ...


class EmbeddingProviderUnavailable(RuntimeError):
    pass


class UnavailableEmbeddingProvider:
    profile = TEST_EMBEDDING_PROFILE
    version = TEST_EMBEDDING_VERSION
    dimension = TEST_EMBEDDING_DIMENSION

    def embed_batch(
        self,
        profile: str,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]:
        raise EmbeddingProviderUnavailable("embedding_provider_unavailable")


class TestHashEmbeddingProvider:
    """Deterministic local adapter for tests; never a runtime default."""

    __test__ = False
    profile = TEST_EMBEDDING_PROFILE
    version = TEST_EMBEDDING_VERSION
    dimension = TEST_EMBEDDING_DIMENSION

    def embed_batch(
        self,
        profile: str,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]:
        if profile != self.profile:
            raise ValueError("embedding_output_invalid")
        return tuple(self._embed(profile, text) for text in texts)

    @staticmethod
    def _embed(profile: str, text: str) -> tuple[float, ...]:
        return deterministic_test_hash_embedding(profile, text)


def deterministic_test_hash_embedding(
    profile: str,
    text: str,
) -> tuple[float, ...]:
    """Return the fixed-profile vector in its pgvector float32 representation."""

    if profile != TEST_EMBEDDING_PROFILE or not isinstance(text, str):
        raise ValueError("embedding_output_invalid")
    digest = hashlib.sha256(f"{profile}\0{text}".encode("utf-8")).digest()
    scale = float((1 << 32) - 1)
    return tuple(
        _float32(
            (int.from_bytes(digest[offset : offset + 4], "big") / scale) * 2.0
            - 1.0
        )
        for offset in range(0, 32, 4)
    )


def _float32(value: float) -> float:
    return struct.unpack("!f", struct.pack("!f", value))[0]
