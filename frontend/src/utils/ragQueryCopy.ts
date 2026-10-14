/**
 * User-facing copy for the "Ask the Reviews" no-answer state (Phase 7 Gate 5, F1).
 *
 * The backend's empty-answer response shape is intentionally identical across
 * several distinct situations (empty retrieval, retrieval failure, generation
 * failure, and answers discarded by citation validation), so this copy must
 * state the outcome only — never assert which cause occurred.
 */

export const RAG_NO_ANSWER_MESSAGE = 'No grounded answer was returned for this question.';

export const RAG_NO_ANSWER_HINT =
  'Try rephrasing your question or choosing a different product.';
