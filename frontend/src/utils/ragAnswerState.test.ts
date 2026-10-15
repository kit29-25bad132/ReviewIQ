import { describe, expect, it } from 'vitest';
import { ragAnswerState } from './ragAnswerState';
import type { RAGQueryResponse } from '../types/ecommerce';

const base: RAGQueryResponse = {
  answer: '',
  evidence: [],
  retrieval_count: 0,
  context_token_estimate: 0,
  model_used: '',
  rag_enabled: true,
  fallback_used: false,
};

describe('ragAnswerState', () => {
  it('A. a non-empty answer on an enabled RAG response is a delivered answer', () => {
    expect(
      ragAnswerState({
        ...base,
        answer: 'Battery lasts two days. [R00669].',
        evidence: [
          { review_id: 'R00669', excerpt: 'battery life is okay', similarity_score: 0.7, rating: 4 },
        ],
        model_used: 'gemini-2.0-flash',
      })
    ).toBe('answer');
  });

  it('B. an enabled response with an empty answer is no_answer — never a fabricated delivery', () => {
    // Covers empty retrieval AND answers discarded by citation/evidence
    // validation: the backend ships answer="" and the UI must not invent one.
    expect(ragAnswerState(base)).toBe('no_answer');
    expect(ragAnswerState({ ...base, answer: '   ' })).toBe('no_answer');
  });

  it('C. a disabled RAG response reports disabled even if fields are default', () => {
    expect(ragAnswerState({ ...base, rag_enabled: false })).toBe('disabled');
    expect(
      ragAnswerState({ ...base, rag_enabled: false, answer: 'should not matter' })
    ).toBe('disabled');
  });
});
