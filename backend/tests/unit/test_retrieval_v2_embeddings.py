from __future__ import annotations

import json
import math

import httpx
import pytest

from app.schemas.retrieval_v2 import EmbeddingProfileV1
from app.services.retrieval_v2_embeddings import (
    BgeM3DenseEncoderV2,
    EmbeddingProviderError,
    LocalBgeM3EmbeddingProviderV2,
    LocalEmbeddingProviderV2,
    OpenRouterEmbeddingProviderV2,
    validate_embedding_batch,
)


def _profile(*, location: str = "local") -> EmbeddingProfileV1:
    return EmbeddingProfileV1(
        version="embedding-profile.v1",
        profile_name=f"stage12.test-{location}-v1",
        model_revision="model-revision-001",
        dimension=3,
        normalization="l2",
        distance_metric="cosine",
        max_input_tokens=384,
        batch_size=4,
        provider_location=location,
        data_residency="synthetic-test-only",
    )


def test_vector_validation_normalizes_float32_and_preserves_order() -> None:
    vectors = validate_embedding_batch(
        ([3.0, 4.0, 0.0], [0.0, 0.0, -2.0]),
        expected_count=2,
        dimension=3,
    )

    assert vectors[0] == pytest.approx((0.6, 0.8, 0.0), abs=1e-6)
    assert vectors[1] == pytest.approx((0.0, 0.0, -1.0), abs=1e-6)
    assert all(
        math.isclose(sum(value * value for value in vector), 1.0, abs_tol=1e-6)
        for vector in vectors
    )


@pytest.mark.parametrize(
    "raw",
    (
        (),
        ([1.0, 2.0],),
        ([0.0, 0.0, 0.0],),
        ([float("nan"), 0.0, 1.0],),
        ([True, 0.0, 1.0],),
    ),
)
def test_vector_validation_rejects_invalid_output(raw: object) -> None:
    with pytest.raises(EmbeddingProviderError) as error:
        validate_embedding_batch(raw, expected_count=1, dimension=3)
    assert error.value.code == "embedding_output_invalid"
    assert (
        repr(error.value) == "EmbeddingProviderError(code='embedding_output_invalid')"
    )


class _RecordingEncoder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def encode(
        self,
        texts: tuple[str, ...],
        *,
        input_kind: str,
    ) -> object:
        self.calls.append((input_kind, texts))
        return tuple((1.0, float(index + 1), 0.5) for index, _ in enumerate(texts))


def test_local_adapter_separates_query_and_document_prefixes() -> None:
    encoder = _RecordingEncoder()
    provider = LocalEmbeddingProviderV2(
        profile=_profile(),
        encoder=encoder,
        query_prefix="query: ",
        document_prefix="passage: ",
    )

    documents = provider.embed_documents(("记录一", "记录二"))
    queries = provider.embed_queries(("查找记录",))

    assert len(documents) == 2
    assert len(queries) == 1
    assert encoder.calls == [
        ("document", ("passage: 记录一", "passage: 记录二")),
        ("query", ("query: 查找记录",)),
    ]


def test_local_adapter_rejects_empty_oversized_or_over_batch_input() -> None:
    provider = LocalEmbeddingProviderV2(
        profile=_profile(),
        encoder=_RecordingEncoder(),
    )
    for texts in ((), ("",), ("one", "two", "three", "four", "five")):
        with pytest.raises(EmbeddingProviderError) as error:
            provider.embed_documents(texts)
        assert error.value.code == "embedding_input_invalid"


class _RecordingSentenceTransformer:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def encode(self, texts: list[str], **kwargs: object) -> object:
        self.calls.append((texts, kwargs))
        return [[1.0, 2.0, 2.0] for _ in texts]


def test_local_bge_m3_provider_uses_dense_cpu_benchmark_contract() -> None:
    model = _RecordingSentenceTransformer()
    provider = LocalBgeM3EmbeddingProviderV2(
        profile=_profile(),
        model=model,
    )

    vectors = provider.embed_documents(("合成记录",))

    assert vectors[0] == pytest.approx((1 / 3, 2 / 3, 2 / 3), abs=1e-6)
    assert model.calls == [
        (
            ["合成记录"],
            {
                "batch_size": 4,
                "convert_to_numpy": True,
                "normalize_embeddings": False,
                "show_progress_bar": False,
            },
        )
    ]
    assert isinstance(provider._encoder, BgeM3DenseEncoderV2)


def test_openrouter_adapter_validates_catalog_policy_and_response_order() -> None:
    requests: list[tuple[str, str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            requests.append((request.method, request.url.path, None))
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "vendor/model",
                            "canonical_slug": "vendor/model-20260729",
                        }
                    ]
                },
            )
        body = json.loads(request.content)
        requests.append((request.method, request.url.path, body))
        return httpx.Response(
            200,
            json={
                "model": "vendor/model",
                "data": [
                    {"index": 1, "embedding": [0.0, 2.0, 0.0]},
                    {"index": 0, "embedding": [3.0, 0.0, 4.0]},
                ],
                "usage": {
                    "prompt_tokens": 7,
                    "total_tokens": 7,
                    "cost": 0.000007,
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenRouterEmbeddingProviderV2(
        profile=_profile(location="remote"),
        api_key="unit-test-key",
        base_url="https://openrouter.test/api/v1",
        model_id="vendor/model",
        expected_canonical_slug="vendor/model-20260729",
        http_client=client,
        timeout_seconds=5.0,
        query_prefix="query: ",
        document_prefix="passage: ",
    )

    vectors = provider.embed_documents(("第一条", "第二条"))

    assert vectors[0] == pytest.approx((0.6, 0.0, 0.8), abs=1e-6)
    assert vectors[1] == pytest.approx((0.0, 1.0, 0.0), abs=1e-6)
    assert provider.consumed_input_tokens == 7
    assert requests[0][:2] == ("GET", "/api/v1/embeddings/models")
    method, path, body = requests[1]
    assert (method, path) == ("POST", "/api/v1/embeddings")
    assert body == {
        "model": "vendor/model",
        "input": ["passage: 第一条", "passage: 第二条"],
        "encoding_format": "float",
        "provider": {
            "allow_fallbacks": False,
            "data_collection": "deny",
            "zdr": True,
        },
    }
    assert provider.estimated_cost_usd == pytest.approx(0.000007)
    assert "unit-test-key" not in repr(provider)
    client.close()


def test_openrouter_adapter_accepts_response_model_identity_case_variation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "baai/bge-m3",
                            "canonical_slug": "baai/bge-m3-20251117",
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "model": "BAAI/bge-m3",
                "data": [{"index": 0, "embedding": [1.0, 0.0, 0.0]}],
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenRouterEmbeddingProviderV2(
        profile=_profile(location="remote"),
        api_key="unit-test-key",
        base_url="https://openrouter.test/api/v1",
        model_id="baai/bge-m3",
        expected_canonical_slug="baai/bge-m3-20251117",
        http_client=client,
    )

    vectors = provider.embed_documents(("synthetic",))

    assert vectors == ((1.0, 0.0, 0.0),)
    client.close()


def test_openrouter_adapter_rejects_revision_drift_before_embedding_post() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "vendor/model", "canonical_slug": "vendor/model-drifted"}
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenRouterEmbeddingProviderV2(
        profile=_profile(location="remote"),
        api_key="unit-test-key",
        base_url="https://openrouter.test/api/v1",
        model_id="vendor/model",
        expected_canonical_slug="vendor/model-20260729",
        http_client=client,
    )

    with pytest.raises(EmbeddingProviderError) as error:
        provider.embed_queries(("不会发送",))
    assert error.value.code == "embedding_model_revision_mismatch"
    assert methods == ["GET"]
    client.close()


def test_openrouter_adapter_rejects_response_model_drift() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "vendor/model",
                            "canonical_slug": "vendor/model-20260729",
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "model": "fallback/other-model",
                "data": [{"index": 0, "embedding": [1.0, 0.0, 0.0]}],
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenRouterEmbeddingProviderV2(
        profile=_profile(location="remote"),
        api_key="unit-test-key",
        base_url="https://openrouter.test/api/v1",
        model_id="vendor/model",
        expected_canonical_slug="vendor/model-20260729",
        http_client=client,
    )

    with pytest.raises(EmbeddingProviderError) as error:
        provider.embed_documents(("synthetic",))
    assert error.value.code == "embedding_model_revision_mismatch"
    client.close()


@pytest.mark.parametrize("status", (401, 402, 429, 500, 529))
def test_openrouter_adapter_maps_http_errors_without_text_or_key(
    status: int,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "vendor/model",
                            "canonical_slug": "vendor/model-20260729",
                        }
                    ]
                },
            )
        return httpx.Response(status, text="echoed-sensitive-input unit-test-key")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenRouterEmbeddingProviderV2(
        profile=_profile(location="remote"),
        api_key="unit-test-key",
        base_url="https://openrouter.test/api/v1",
        model_id="vendor/model",
        expected_canonical_slug="vendor/model-20260729",
        http_client=client,
    )

    with pytest.raises(EmbeddingProviderError) as error:
        provider.embed_documents(("echoed-sensitive-input",))
    assert error.value.code in {
        "embedding_provider_auth_failed",
        "embedding_provider_payment_required",
        "embedding_provider_rate_limited",
        "embedding_provider_unavailable",
    }
    rendered = repr(error.value) + str(error.value)
    assert "echoed-sensitive-input" not in rendered
    assert "unit-test-key" not in rendered
    client.close()
