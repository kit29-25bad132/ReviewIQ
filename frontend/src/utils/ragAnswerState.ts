import type { RAGQueryResponse } from '../types/ecommerce';

/**
 * Honest rendering state for one `/rag-query` response.
 *
 * The backend legitimately returns an empty `answer` in three situations —
 * RAG disabled, empty retrieval, or the answer discarded by citation/evidence
 * validation (an empty answer is never a grounded delivery). The UI must
 * distinguish "disabled" from "no grounded answer" and must never present an
 * empty answer as content.
 */
export type RagAnswerState = 'disabled' | 'no_answer' | 'answer';

export function ragAnswerState(response: RAGQueryResponse): RagAnswerState {
  if (!response.rag_enabled) {
    return 'disabled';
  }
  if (!response.answer.trim()) {
    return 'no_answer';
  }
  return 'answer';
}
