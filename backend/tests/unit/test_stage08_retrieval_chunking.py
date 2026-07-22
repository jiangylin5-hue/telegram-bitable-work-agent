import ast
import hashlib
from pathlib import Path

import pytest

from app.services.stage08_retrieval_chunking import (
    canonicalize_knowledge_text,
    chunk_knowledge_projection,
)


def test_canonicalize_knowledge_text_normalizes_nfc_newlines_and_c0_controls() -> None:
    text = "Cafe\u0301\r\nA\rB\x00\x01\tC"

    assert canonicalize_knowledge_text(text) == "Café\nA\nB\tC"


def test_canonicalize_knowledge_text_rejects_empty_result_with_safe_code() -> None:
    with pytest.raises(ValueError, match="^knowledge_source_text_empty$"):
        canonicalize_knowledge_text("\x00\x01")


def test_chunker_uses_exact_1200_code_point_limit_and_200_overlap() -> None:
    exact = chunk_knowledge_projection("甲" * 1_200)
    overlapped = chunk_knowledge_projection("甲" * 2_200)

    assert len(exact) == 1
    assert len(exact[0].chunk_text or "") == 1_200
    assert [len(chunk.chunk_text or "") for chunk in overlapped] == [1_200, 1_200]
    assert overlapped[0].chunk_text == "甲" * 1_200
    assert overlapped[1].chunk_text == "甲" * 1_200
    assert (overlapped[0].chunk_text or "")[-200:] == (
        overlapped[1].chunk_text or ""
    )[:200]


def test_chunker_never_splits_inside_a_python_code_point() -> None:
    chunks = chunk_knowledge_projection("🚀" * 1_201)

    assert chunks[0].chunk_text == "🚀" * 1_200
    assert chunks[1].chunk_text == "🚀" * 201


def test_chunker_repeated_output_hash_and_ordinals_are_stable() -> None:
    text = ("客户 Acme42 已批准\n" * 180).strip()

    first = chunk_knowledge_projection(text)
    second = chunk_knowledge_projection(text)

    assert first == second
    assert [chunk.ordinal for chunk in first] == list(range(len(first)))
    assert all(chunk.source_version == 1 for chunk in first)
    assert all(chunk.status == "pending" for chunk in first)
    assert all(
        chunk.chunk_hash
        == hashlib.sha256((chunk.chunk_text or "").encode("utf-8")).hexdigest()
        for chunk in first
    )


def test_chunker_emits_cjk_bigrams_and_normalized_latin_digit_terms() -> None:
    chunk = chunk_knowledge_projection("甲乙丙 Café42 CAFÉ42 2026")[0]

    assert "甲乙" in chunk.keyword_terms
    assert "乙丙" in chunk.keyword_terms
    assert "café42" in chunk.keyword_terms
    assert "2026" in chunk.keyword_terms
    assert chunk.keyword_terms.count("café42") == 1


def test_chunker_caps_terms_at_256_and_each_term_at_64_code_points() -> None:
    cjk_sequence = "".join(chr(0x4E00 + offset) for offset in range(258))
    long_latin = "A" * 80
    chunks = chunk_knowledge_projection(f"{cjk_sequence} {long_latin}")

    assert len(chunks[0].keyword_terms) == 256
    assert all(len(term) <= 64 for term in chunks[0].keyword_terms)
    long_token_chunk = chunk_knowledge_projection(long_latin)[0]
    assert long_token_chunk.keyword_terms == ("a" * 64,)


def test_chunker_accepts_exact_source_cap_as_exactly_1000_chunks() -> None:
    chunks = chunk_knowledge_projection("甲" * 1_000_000)

    assert len(chunks) == 1_000
    assert chunks[-1].ordinal == 999
    assert len(chunks[-1].chunk_text or "") == 1_000


def test_chunker_rejects_over_source_cap_without_partial_output() -> None:
    with pytest.raises(ValueError, match="^knowledge_source_text_limit_exceeded$"):
        chunk_knowledge_projection("甲" * 1_000_001)


def test_chunking_module_has_no_external_or_provider_imports() -> None:
    module_path = (
        Path(__file__).parents[2]
        / "app"
        / "services"
        / "stage08_retrieval_chunking.py"
    )
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }

    assert imported_roots <= {"__future__", "hashlib", "unicodedata", "app"}
