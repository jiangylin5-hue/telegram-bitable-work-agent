from __future__ import annotations

import hashlib
import unicodedata

from app.runtime.stage08_retrieval_contracts import KnowledgeChunkProjection


_MAX_CHUNK_CODE_POINTS = 1_200
_CHUNK_OVERLAP_CODE_POINTS = 200
_CHUNK_STEP_CODE_POINTS = (
    _MAX_CHUNK_CODE_POINTS - _CHUNK_OVERLAP_CODE_POINTS
)
_MAX_CHUNKS = 1_000
_MAX_SOURCE_CODE_POINTS = 1_000_000
_MAX_KEYWORD_TERMS = 256
_MAX_KEYWORD_TERM_CODE_POINTS = 64


def canonicalize_knowledge_text(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError("knowledge_source_text_invalid")
    normalized = unicodedata.normalize(
        "NFC",
        text.replace("\r\n", "\n").replace("\r", "\n"),
    )
    canonical = "".join(
        character
        for character in normalized
        if ord(character) >= 0x20 or character in {"\n", "\t"}
    )
    if not canonical.strip():
        raise ValueError("knowledge_source_text_empty")
    return canonical


def chunk_knowledge_projection(text: str) -> tuple[KnowledgeChunkProjection, ...]:
    canonical = canonicalize_knowledge_text(text)
    source_length = len(canonical)
    if source_length > _MAX_SOURCE_CODE_POINTS:
        raise ValueError("knowledge_source_text_limit_exceeded")

    chunk_count = _chunk_count(source_length)
    if chunk_count > _MAX_CHUNKS:
        raise ValueError("knowledge_source_text_limit_exceeded")

    chunks: list[KnowledgeChunkProjection] = []
    for ordinal in range(chunk_count):
        start = ordinal * _CHUNK_STEP_CODE_POINTS
        chunk_text = canonical[start : start + _MAX_CHUNK_CODE_POINTS]
        chunks.append(
            KnowledgeChunkProjection(
                source_version=1,
                ordinal=ordinal,
                chunk_text=chunk_text,
                chunk_hash=hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
                keyword_terms=_keyword_terms(chunk_text),
                embedding_profile=None,
                embedding_version=None,
                status="pending",
            )
        )
    return tuple(chunks)


def _chunk_count(source_length: int) -> int:
    if source_length <= _MAX_CHUNK_CODE_POINTS:
        return 1
    remaining = source_length - _MAX_CHUNK_CODE_POINTS
    return 1 + (remaining + _CHUNK_STEP_CODE_POINTS - 1) // _CHUNK_STEP_CODE_POINTS


def _keyword_terms(text: str) -> tuple[str, ...]:
    terms: list[str] = []
    seen: set[str] = set()
    index = 0
    while index < len(text) and len(terms) < _MAX_KEYWORD_TERMS:
        character = text[index]
        if _is_cjk(character):
            end = index + 1
            while end < len(text) and _is_cjk(text[end]):
                end += 1
            sequence = text[index:end]
            for offset in range(len(sequence) - 1):
                _append_term(sequence[offset : offset + 2], terms, seen)
                if len(terms) == _MAX_KEYWORD_TERMS:
                    break
            index = end
            continue
        if _is_latin_or_digit(character):
            end = index + 1
            while end < len(text) and _is_latin_or_digit(text[end]):
                end += 1
            token = text[index:end].casefold()[:_MAX_KEYWORD_TERM_CODE_POINTS]
            _append_term(token, terms, seen)
            index = end
            continue
        index += 1
    return tuple(terms)


def _append_term(term: str, terms: list[str], seen: set[str]) -> None:
    if term and term not in seen and len(terms) < _MAX_KEYWORD_TERMS:
        terms.append(term)
        seen.add(term)


def _is_cjk(character: str) -> bool:
    code_point = ord(character)
    return (
        0x3400 <= code_point <= 0x4DBF
        or 0x4E00 <= code_point <= 0x9FFF
        or 0xF900 <= code_point <= 0xFAFF
        or 0x20000 <= code_point <= 0x2FA1F
        or 0x30000 <= code_point <= 0x323AF
    )


def _is_latin_or_digit(character: str) -> bool:
    if character.isdecimal():
        return True
    return "LATIN" in unicodedata.name(character, "")
