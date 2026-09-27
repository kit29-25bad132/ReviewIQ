"""Deterministic, versioned cache keys (V2-P9).

Every cache key is ``SHA-256(canonical_json(key_material))``:

- stable field ordering (``sort_keys=True``),
- stable serialization (compact separators, ``ensure_ascii=True``),
- explicit UTF-8 encoding,
- no ``hash()``, no memory addresses, no timestamps, no randomness.

Version constants (maintenance rules):

- ``CACHE_SCHEMA_VERSION`` — bump whenever cache serialization or storage
  semantics change (payload envelope, column meaning, key algorithm) OR when
  a change alters the MEANING of an already-cached result without changing
  its prompt or response schema. That includes: grounding rules,
  evidence-support rules, aspect-support rules, result post-processing, and
  any normalization or deterministic transformation that changes the final
  validated ``ReviewAnalysis`` / ``AISummaryResponse``. Review this rule on
  every change to result semantics — but do NOT blindly bump it for
  unrelated code changes: prompt/instruction edits use ``PROMPT_VERSION``,
  response-shape changes are already bound by the schema identity digest,
  embedding-preprocessing changes use ``PREPROCESS_VERSION``, and RAG
  configuration changes are bound by the RAG config digest inside the key.
- ``PROMPT_VERSION`` — bump whenever the effective analysis/summary prompt or
  any system instruction changes (``SYSTEM_INSTRUCTION``,
  ``SUMMARY_SYSTEM_INSTRUCTION``, ``CONTEXT_SYSTEM_RULES``, ``BASE_PROMPT``…).
- ``PREPROCESS_VERSION`` — bump whenever embedding preprocessing semantics
  change (``preprocess_review_text`` behavior).

The application version is deliberately NOT used as a substitute: releases can
ship without prompt changes and prompt edits can ship without a version bump.

Provider/model/routing/retry are NOT key material: the validated, grounded
application result is provider-neutral (ADR-011), so a successful fallback
result stays reusable when the primary provider recovers. Provider/model
provenance is stored separately, server-side only.
"""

import hashlib
import json
from typing import Any, Mapping, Optional

#: Bump when cache payload/storage semantics change.
CACHE_SCHEMA_VERSION = "1"
#: Bump when the effective prompt or any system instruction changes.
PROMPT_VERSION = "1"
#: Bump when embedding preprocessing semantics change.
PREPROCESS_VERSION = "1"

# RAGConfig field names hashed into the RAG configuration digest. Duck-typed so
# this module never imports the RAG package (keeps the cache layer independent).
_RAG_CONFIG_FIELDS = (
    "enabled",
    "top_k",
    "similarity_threshold",
    "max_context_reviews",
    "max_context_chars",
    "max_review_chars",
)


def canonical_key(material: Mapping[str, Any]) -> str:
    """Return the SHA-256 hex digest of canonically serialized key material."""
    payload = json.dumps(
        material, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_hex(text: str) -> str:
    """SHA-256 hex digest of a UTF-8 string (for digests nested in keys)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def response_schema_identity(schema: Any) -> str:
    """Stable identity for a response schema (class name + schema digest).

    Duck-typed so this module never imports Pydantic: works with any class
    exposing ``model_json_schema()`` (Pydantic v2) and degrades to the class
    name alone for anything else.
    """
    if schema is None:
        return "none"
    name = getattr(schema, "__name__", type(schema).__name__)
    try:
        json_schema = schema.model_json_schema()
    except Exception:
        return name
    return f"{name}:{sha256_hex(json.dumps(json_schema, sort_keys=True, default=str))}"


def rag_config_digest(rag_config: Any) -> str:
    """Deterministic digest of the RAG configuration (``None`` -> empty digest).

    Duck-typed over dataclass-style attributes so this module stays free of
    RAG package imports; missing fields hash as ``None`` rather than raising.
    """
    if rag_config is None:
        return canonical_key({})
    material = {field: getattr(rag_config, field, None) for field in _RAG_CONFIG_FIELDS}
    return canonical_key(material)


def analysis_cache_key(
    *,
    task: str,
    system_instruction: str,
    response_schema: Any,
    temperature: float,
    normalized_review_text: str,
    rag_enabled: bool,
    rag_config: Any,
) -> str:
    """Key for a cached review-analysis result.

    Binds everything that shapes the prompt/result EXCEPT provider/model
    (provider-neutral by design) and retrieved context (bound separately via
    the RAG corpus token + context digest, ADR-011).
    """
    return canonical_key(
        {
            "cache_schema": CACHE_SCHEMA_VERSION,
            "prompt_version": PROMPT_VERSION,
            "task": str(task),
            "system": sha256_hex(system_instruction or ""),
            "schema": response_schema_identity(response_schema),
            "temperature": float(temperature),
            "review": normalized_review_text,
            "rag_enabled": bool(rag_enabled),
            "rag_config": rag_config_digest(rag_config),
        }
    )


def summary_cache_key(
    *,
    task: str,
    system_instruction: str,
    response_schema: Any,
    temperature: float,
    prompt: str,
) -> str:
    """Key for a cached product-summary result (no RAG in this path).

    The composed prompt is digested, never stored in the key material itself.
    """
    return canonical_key(
        {
            "cache_schema": CACHE_SCHEMA_VERSION,
            "prompt_version": PROMPT_VERSION,
            "task": str(task),
            "system": sha256_hex(system_instruction or ""),
            "schema": response_schema_identity(response_schema),
            "temperature": float(temperature),
            "prompt": sha256_hex(prompt or ""),
            "rag_enabled": False,
            "rag_config": canonical_key({}),
        }
    )


def embedding_cache_key(
    *,
    text: str,
    task_type: str,
    provider: str,
    model: str,
    dimension: int,
) -> str:
    """Key for a cached embedding vector.

    ``task_type`` is a mandatory namespace: RETRIEVAL_DOCUMENT and
    RETRIEVAL_QUERY produce different vectors for identical text and MUST
    NEVER share a cache entry.
    """
    return canonical_key(
        {
            "cache_schema": CACHE_SCHEMA_VERSION,
            "preprocess_version": PREPROCESS_VERSION,
            "provider": str(provider),
            "model": str(model),
            "dimension": int(dimension),
            "task_type": str(task_type),
            # Post-preprocessing text only: the provider never sees raw input.
            "text": text,
        }
    )
