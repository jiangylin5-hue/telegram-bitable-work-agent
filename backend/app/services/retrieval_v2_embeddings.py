"""Strict Stage12-D vector providers with redacted failures."""

from __future__ import annotations

from collections.abc import Sequence
import math
import struct
from typing import Protocol

import httpx

from app.schemas.retrieval_v2 import EmbeddingProfileV1


VectorBatch = tuple[tuple[float, ...], ...]


class EmbeddingProviderError(RuntimeError):
    """A stable provider error that never includes inputs or credentials."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)

    def __repr__(self) -> str:
        return f"EmbeddingProviderError(code={self.code!r})"


class LocalVectorEncoder(Protocol):
    def encode(self, texts: tuple[str, ...], *, input_kind: str) -> object: ...


class SentenceTransformerModel(Protocol):
    def encode(self, texts: list[str], **kwargs: object) -> object: ...


def _float32(value: float) -> float:
    return struct.unpack("!f", struct.pack("!f", value))[0]


def validate_embedding_batch(
    raw_vectors: object,
    *,
    expected_count: int,
    dimension: int,
) -> VectorBatch:
    """Validate, float32-cast and L2-normalize a provider batch."""

    try:
        if hasattr(raw_vectors, "tolist"):
            raw_vectors = raw_vectors.tolist()
        if not isinstance(raw_vectors, Sequence) or isinstance(
            raw_vectors, (str, bytes)
        ):
            raise ValueError
        if len(raw_vectors) != expected_count:
            raise ValueError
        normalized: list[tuple[float, ...]] = []
        for raw_vector in raw_vectors:
            if hasattr(raw_vector, "tolist"):
                raw_vector = raw_vector.tolist()
            if not isinstance(raw_vector, Sequence) or isinstance(
                raw_vector, (str, bytes)
            ):
                raise ValueError
            if len(raw_vector) != dimension:
                raise ValueError
            values: list[float] = []
            for value in raw_vector:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError
                cast = _float32(float(value))
                if not math.isfinite(cast):
                    raise ValueError
                values.append(cast)
            magnitude = math.sqrt(sum(value * value for value in values))
            if not math.isfinite(magnitude) or magnitude <= 0.0:
                raise ValueError
            vector = tuple(_float32(value / magnitude) for value in values)
            if not all(math.isfinite(value) for value in vector):
                raise ValueError
            normalized.append(vector)
        return tuple(normalized)
    except (OverflowError, TypeError, ValueError):
        raise EmbeddingProviderError("embedding_output_invalid") from None


def _validated_texts(
    texts: object,
    *,
    profile: EmbeddingProfileV1,
) -> tuple[str, ...]:
    if (
        not isinstance(texts, tuple)
        or not texts
        or len(texts) > profile.batch_size
        or any(not isinstance(text, str) or not text.strip() for text in texts)
    ):
        raise EmbeddingProviderError("embedding_input_invalid")
    return texts


class LocalEmbeddingProviderV2:
    def __init__(
        self,
        *,
        profile: EmbeddingProfileV1,
        encoder: LocalVectorEncoder,
        query_prefix: str = "",
        document_prefix: str = "",
    ) -> None:
        if profile.provider_location != "local":
            raise EmbeddingProviderError("embedding_profile_invalid")
        self.profile = profile
        self._encoder = encoder
        self._query_prefix = query_prefix
        self._document_prefix = document_prefix
        self.consumed_input_tokens = 0
        self.estimated_cost_usd = 0.0

    def __repr__(self) -> str:
        return (
            "LocalEmbeddingProviderV2(" f"profile_name={self.profile.profile_name!r})"
        )

    def embed_documents(self, texts: tuple[str, ...]) -> VectorBatch:
        return self._embed(texts, input_kind="document", prefix=self._document_prefix)

    def embed_queries(self, texts: tuple[str, ...]) -> VectorBatch:
        return self._embed(texts, input_kind="query", prefix=self._query_prefix)

    def _embed(
        self,
        texts: tuple[str, ...],
        *,
        input_kind: str,
        prefix: str,
    ) -> VectorBatch:
        validated = _validated_texts(texts, profile=self.profile)
        prepared = tuple(f"{prefix}{text}" for text in validated)
        try:
            raw_vectors = self._encoder.encode(prepared, input_kind=input_kind)
        except EmbeddingProviderError:
            raise
        except Exception:
            raise EmbeddingProviderError("embedding_provider_unavailable") from None
        return validate_embedding_batch(
            raw_vectors,
            expected_count=len(prepared),
            dimension=self.profile.dimension,
        )


class BgeM3DenseEncoderV2:
    """Dense-only bridge for a pinned SentenceTransformer BGE-M3 model."""

    def __init__(
        self,
        *,
        model: SentenceTransformerModel,
        batch_size: int,
    ) -> None:
        self._model = model
        self._batch_size = batch_size

    def encode(self, texts: tuple[str, ...], *, input_kind: str) -> object:
        if input_kind not in {"document", "query"}:
            raise EmbeddingProviderError("embedding_input_invalid")
        return self._model.encode(
            list(texts),
            batch_size=self._batch_size,
            convert_to_numpy=True,
            normalize_embeddings=False,
            show_progress_bar=False,
        )


class LocalBgeM3EmbeddingProviderV2(LocalEmbeddingProviderV2):
    def __init__(
        self,
        *,
        profile: EmbeddingProfileV1,
        model: SentenceTransformerModel,
    ) -> None:
        super().__init__(
            profile=profile,
            encoder=BgeM3DenseEncoderV2(
                model=model,
                batch_size=profile.batch_size,
            ),
        )


class OpenRouterEmbeddingProviderV2:
    def __init__(
        self,
        *,
        profile: EmbeddingProfileV1,
        api_key: str,
        base_url: str,
        model_id: str,
        expected_canonical_slug: str,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
        query_prefix: str = "",
        document_prefix: str = "",
    ) -> None:
        if (
            profile.provider_location != "remote"
            or not api_key
            or not base_url
            or not model_id
            or not expected_canonical_slug
        ):
            raise EmbeddingProviderError("embedding_profile_invalid")
        self.profile = profile
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model_id = model_id
        self._expected_canonical_slug = expected_canonical_slug
        self._query_prefix = query_prefix
        self._document_prefix = document_prefix
        self._client = http_client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = http_client is None
        self._catalog_validated = False
        self.consumed_input_tokens = 0
        self.estimated_cost_usd = 0.0

    def __repr__(self) -> str:
        return (
            "OpenRouterEmbeddingProviderV2("
            f"profile_name={self.profile.profile_name!r}, model_id={self._model_id!r})"
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def embed_documents(self, texts: tuple[str, ...]) -> VectorBatch:
        return self._embed(texts, prefix=self._document_prefix)

    def embed_queries(self, texts: tuple[str, ...]) -> VectorBatch:
        return self._embed(texts, prefix=self._query_prefix)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _validate_catalog(self) -> None:
        if self._catalog_validated:
            return
        try:
            response = self._client.get(
                f"{self._base_url}/embeddings/models",
                headers=self._headers(),
            )
        except httpx.HTTPError:
            raise EmbeddingProviderError("embedding_provider_unavailable") from None
        self._raise_for_status(response)
        try:
            data = response.json()["data"]
            model = next(item for item in data if item.get("id") == self._model_id)
            canonical_slug = model["canonical_slug"]
        except (KeyError, StopIteration, TypeError, ValueError):
            raise EmbeddingProviderError("embedding_model_revision_mismatch") from None
        if canonical_slug != self._expected_canonical_slug:
            raise EmbeddingProviderError("embedding_model_revision_mismatch")
        self._catalog_validated = True

    def _embed(self, texts: tuple[str, ...], *, prefix: str) -> VectorBatch:
        validated = _validated_texts(texts, profile=self.profile)
        prepared = tuple(f"{prefix}{text}" for text in validated)
        self._validate_catalog()
        payload = {
            "model": self._model_id,
            "input": list(prepared),
            "encoding_format": "float",
            "provider": {
                "allow_fallbacks": False,
                "data_collection": "deny",
                "zdr": True,
            },
        }
        try:
            response = self._client.post(
                f"{self._base_url}/embeddings",
                headers=self._headers(),
                json=payload,
            )
        except httpx.HTTPError:
            raise EmbeddingProviderError("embedding_provider_unavailable") from None
        self._raise_for_status(response)
        try:
            body = response.json()
            response_model = body["model"]
            if not isinstance(response_model, str) or response_model.casefold() not in {
                self._model_id.casefold(),
                self._expected_canonical_slug.casefold(),
            }:
                raise EmbeddingProviderError("embedding_model_revision_mismatch")
            rows = body["data"]
            ordered = sorted(rows, key=lambda item: item["index"])
            if [item["index"] for item in ordered] != list(range(len(prepared))):
                raise ValueError
            raw_vectors = tuple(item["embedding"] for item in ordered)
            usage = body.get("usage") or {}
            input_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0))
            if isinstance(input_tokens, bool) or not isinstance(input_tokens, int):
                raise ValueError
            raw_cost = usage.get("cost", 0.0)
            if isinstance(raw_cost, bool):
                raise ValueError
            request_cost = float(raw_cost)
            if not math.isfinite(request_cost) or request_cost < 0.0:
                raise ValueError
        except EmbeddingProviderError:
            raise
        except (KeyError, TypeError, ValueError):
            raise EmbeddingProviderError("embedding_output_invalid") from None
        vectors = validate_embedding_batch(
            raw_vectors,
            expected_count=len(prepared),
            dimension=self.profile.dimension,
        )
        self.consumed_input_tokens += input_tokens
        self.estimated_cost_usd += request_cost
        return vectors

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        if response.status_code == 401:
            code = "embedding_provider_auth_failed"
        elif response.status_code == 402:
            code = "embedding_provider_payment_required"
        elif response.status_code == 429:
            code = "embedding_provider_rate_limited"
        else:
            code = "embedding_provider_unavailable"
        raise EmbeddingProviderError(code)
