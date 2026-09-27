"""Validated LLM response cache (V2-P9).

Caches the *validated application result* of the two LLM consumers:

- review analysis  -> ``models.review.ReviewAnalysis``
- product summary  -> ``models.ecommerce.AISummaryResponse``
Read path (never trust stored JSON):

1. decode the row, 2. verify envelope/expiry, 3. verify the RAG corpus token
when RAG is enabled, 4. validate with the owning Pydantic model, 5. return
the validated instance — or ``None`` (cache miss). Raw JSON never reaches the
API.

Grounding/digest invariants (ADR-011):

- Evidence grounding and P8 aspect support run BEFORE the cache write; on a
  hit grounding is deliberately NOT re-run — it is deterministic/idempotent
  for the review text that the cache key already binds, and the stored result
  is revalidated through the authoritative Pydantic model on every read.
- The corpus token is the AUTHORITATIVE RAG freshness guard;
  ``rag_context_digest`` is diagnostic/provenance metadata only (the rendered
  context is never stored, so verifying it on read would require re-running
  retrieval — a hit must stay cheaper than a miss). The RAG configuration
  digest is part of the cache key, so a config change shifts the key.

Failure policy:

- Any cache/DB failure is a cache miss and any malformed entry is deleted then
  treated as a miss (fail open): the cache never turns a working ReviewIQ
  request into an error.
- EXCEPTION — RAG corpus-token verification fails CLOSED: when RAG is enabled
  and the LIVE corpus token cannot be obtained (or does not match the stored
  one), the result is a cache miss and the normal RAG pipeline runs. A
  possibly-stale RAG result is never served.

Keys are provider/model independent (the validated, grounded result is
provider-neutral — ADR-011), so a successful fallback result stays reusable
when the primary provider recovers. Provider/model provenance may be stored
internally and is NEVER returned through the API.

Never stored: credentials, DSNs, prompts, retrieved context, provider error
text, token counts, cost/billing/rate data, request headers.

Logging is limited to operation type, task identifier, and a short key hash
prefix — never review text, prompts, context, payloads, or secrets.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from models.ecommerce import AISummaryResponse
from models.review import ReviewAnalysis
from services.cache.config import CacheConfig
from services.cache.keys import (
    CACHE_SCHEMA_VERSION,
    analysis_cache_key,
    summary_cache_key,
)

logger = logging.getLogger(__name__)

#: Envelope discriminator stored inside ``payload`` (defence in depth: the key
#: already encodes the task, so a cross-kind row can only exist via corruption).
ANALYSIS_KIND = "review_analysis"
SUMMARY_KIND = "dataset_summary"

_MODELS = {
    ANALYSIS_KIND: ReviewAnalysis,
    SUMMARY_KIND: AISummaryResponse,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _rag_enabled(rag_config: Any) -> bool:
    """Duck-typed RAG flag so the cache never imports the RAG package."""
    return bool(getattr(rag_config, "enabled", False))


class LLMCache:
    """Reads/writes validated LLM results in the ``ai_response_cache`` table.

    ``store``/``config`` are injectable for tests; by default the store is
    built lazily on first *enabled* operation (a disabled cache never opens a
    database connection) and configuration is resolved from the environment on
    every call (RAGConfig/RetryPolicy-style call-time resolution).
    """

    def __init__(self, store: Any = None, config: Optional[CacheConfig] = None) -> None:
        self._store = store
        self._config = config

    @property
    def config(self) -> CacheConfig:
        return self._config if self._config is not None else CacheConfig.from_env()

    @property
    def store(self) -> Any:
        if self._store is None:
            # Lazy + local: keeps this module importable without the retrieval
            # package (no import cycle) and touches no DB until a live op runs.
            from services.cache.store import build_cache_store

            self._store = build_cache_store()
        return self._store

    # -- keys ---------------------------------------------------------------

    def analysis_key(
        self,
        *,
        review_text: str,
        task: str,
        system_instruction: str,
        temperature: float,
        rag_config: Any,
    ) -> str:
        return analysis_cache_key(
            task=task,
            system_instruction=system_instruction,
            response_schema=ReviewAnalysis,
            temperature=temperature,
            normalized_review_text=review_text,
            rag_enabled=_rag_enabled(rag_config),
            rag_config=rag_config,
        )

    def summary_key(
        self,
        *,
        prompt: str,
        task: str,
        system_instruction: str,
        temperature: float,
    ) -> str:
        return summary_cache_key(
            task=task,
            system_instruction=system_instruction,
            response_schema=AISummaryResponse,
            temperature=temperature,
            prompt=prompt,
        )

    # -- reads --------------------------------------------------------------

    def get_analysis(
        self,
        *,
        review_text: str,
        task: str,
        system_instruction: str,
        temperature: float,
        rag_config: Any,
    ) -> Optional[ReviewAnalysis]:
        try:
            config = self.config
            if not config.llm_enabled:
                return None
            return self._read(  # type: ignore[return-value]
                key=self.analysis_key(
                    review_text=review_text,
                    task=task,
                    system_instruction=system_instruction,
                    temperature=temperature,
                    rag_config=rag_config,
                ),
                kind=ANALYSIS_KIND,
                rag_enabled=_rag_enabled(rag_config),
                task=task,
            )
        except Exception as exc:  # fail open: lookup never blocks a request
            logger.warning("LLM cache lookup failed (%s).", type(exc).__name__)
            return None

    def get_summary(
        self,
        *,
        prompt: str,
        task: str,
        system_instruction: str,
        temperature: float,
    ) -> Optional[AISummaryResponse]:
        try:
            config = self.config
            if not config.llm_enabled:
                return None
            return self._read(  # type: ignore[return-value]
                key=self.summary_key(
                    prompt=prompt,
                    task=task,
                    system_instruction=system_instruction,
                    temperature=temperature,
                ),
                kind=SUMMARY_KIND,
                rag_enabled=False,
                task=task,
            )
        except Exception as exc:  # fail open: lookup never blocks a request
            logger.warning("LLM cache lookup failed (%s).", type(exc).__name__)
            return None

    def _read(
        self, *, key: str, kind: str, rag_enabled: bool, task: str
    ) -> Optional[Any]:
        model = _MODELS[kind]
        try:
            from services.cache.store import RESPONSE_TABLE

            row = self.store.get(RESPONSE_TABLE, key)
            if row is None:
                logger.info("LLM cache miss (%s, key=%s).", task, key[:12])
                return None
            if not self._is_fresh(row):
                self._delete(RESPONSE_TABLE, key)
                logger.info("LLM cache miss/expired (%s, key=%s).", task, key[:12])
                return None
            if rag_enabled and not self._rag_token_matches(row):
                # Fail CLOSED: never serve a possibly-stale RAG result. The
                # row is kept — it stays valid for an unchanged corpus.
                logger.info(
                    "LLM cache miss/rag-corpus (%s, key=%s).", task, key[:12]
                )
                return None
            result = self._decode(row, kind=kind, model=model, key=key)
            if result is None:
                logger.info("LLM cache miss/malformed (%s, key=%s).", task, key[:12])
                return None
            logger.info("LLM cache hit (%s, key=%s).", task, key[:12])
            return result
        except Exception as exc:  # fail open: any failure == cache miss
            logger.warning("LLM cache read failed (%s).", type(exc).__name__)
            return None

    def _is_fresh(self, row: Dict[str, Any]) -> bool:
        expires = row.get("expires_at")
        if not isinstance(expires, datetime):
            return False
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires > _utcnow()

    def _rag_token_matches(self, row: Dict[str, Any]) -> bool:
        stored = row.get("corpus_token")
        if not stored:
            return False
        live = self.store.corpus_token()  # None => lookup failed => miss
        return live is not None and live == stored

    def _decode(self, row: Dict[str, Any], *, kind: str, model: Any, key: str) -> Any:
        """Validate a stored row; malformed entries are deleted and ignored."""
        from services.cache.store import RESPONSE_TABLE

        payload = row.get("payload")
        try:
            if not isinstance(payload, dict):
                raise ValueError("payload is not an object")
            if payload.get("kind") != kind:
                raise ValueError("payload kind mismatch")
            if str(payload.get("cache_schema")) != str(CACHE_SCHEMA_VERSION):
                raise ValueError("payload cache schema mismatch")
            result = model.model_validate(payload.get("result"))
        except Exception:
            # Malformed cache entry: delete it, then treat as a miss.
            self._delete(RESPONSE_TABLE, key)
            return None
        return result

    # -- writes -------------------------------------------------------------

    def put_analysis(
        self,
        *,
        review_text: str,
        task: str,
        system_instruction: str,
        temperature: float,
        rag_config: Any,
        analysis: ReviewAnalysis,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        fallback: bool = False,
        rag_context_digest: Optional[str] = None,
    ) -> None:
        try:
            config = self.config
            if not config.llm_enabled or analysis is None:
                return
            rag_enabled = _rag_enabled(rag_config)
            corpus_token = None
            if rag_enabled:
                corpus_token = self.store.corpus_token()
                if not corpus_token:
                    # Without the live token the entry could never be verified
                    # on read: storing it would only create unusable rows.
                    logger.info(
                        "LLM cache write skipped (rag token unavailable)."
                    )
                    return
            self._write(
                key=self.analysis_key(
                    review_text=review_text,
                    task=task,
                    system_instruction=system_instruction,
                    temperature=temperature,
                    rag_config=rag_config,
                ),
                kind=ANALYSIS_KIND,
                task=task,
                result=analysis,
                ttl_seconds=config.llm_ttl_for(rag_enabled),
                provenance={
                    "task": task,
                    "provider": provider,
                    "model": model_name,
                    "fallback": bool(fallback),
                },
                rag_context_digest=rag_context_digest if rag_enabled else None,
                corpus_token=corpus_token,
            )
        except Exception as exc:  # a failed write must never block a request
            logger.warning("LLM cache write failed (%s).", type(exc).__name__)

    def put_summary(
        self,
        *,
        prompt: str,
        task: str,
        system_instruction: str,
        temperature: float,
        summary: AISummaryResponse,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        fallback: bool = False,
    ) -> None:
        try:
            config = self.config
            if not config.llm_enabled or summary is None:
                return
            self._write(
                key=self.summary_key(
                    prompt=prompt,
                    task=task,
                    system_instruction=system_instruction,
                    temperature=temperature,
                ),
                kind=SUMMARY_KIND,
                task=task,
                result=summary,
                ttl_seconds=config.llm_ttl_seconds,
                provenance={
                    "task": task,
                    "provider": provider,
                    "model": model_name,
                    "fallback": bool(fallback),
                },
                rag_context_digest=None,
                corpus_token=None,
            )
        except Exception as exc:  # a failed write must never block a request
            logger.warning("LLM cache write failed (%s).", type(exc).__name__)

    def _write(
        self,
        *,
        key: str,
        kind: str,
        task: str,
        result: Any,
        ttl_seconds: int,
        provenance: Dict[str, Any],
        rag_context_digest: Optional[str],
        corpus_token: Optional[str],
    ) -> None:
        try:
            from services.cache.store import RESPONSE_TABLE

            now = _utcnow()
            self.store.put(
                RESPONSE_TABLE,
                {
                    "cache_key": key,
                    "payload": {
                        "kind": kind,
                        "cache_schema": CACHE_SCHEMA_VERSION,
                        "result": result.model_dump(mode="json"),
                    },
                    "provenance": provenance,
                    "rag_context_digest": rag_context_digest,
                    "corpus_token": corpus_token,
                    "created_at": now,
                    "expires_at": now + timedelta(seconds=ttl_seconds),
                },
            )
            logger.info("LLM cache write (%s, key=%s).", task, key[:12])
        except Exception as exc:  # fail open: a failed write never blocks
            logger.warning("LLM cache write failed (%s).", type(exc).__name__)

    def _delete(self, table: str, key: str) -> None:
        try:
            self.store.delete(table, key)
        except Exception as exc:
            logger.warning("LLM cache delete failed (%s).", type(exc).__name__)


__all__ = ["ANALYSIS_KIND", "SUMMARY_KIND", "LLMCache"]
