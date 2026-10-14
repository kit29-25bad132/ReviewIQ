import { describe, expect, it } from 'vitest';
import { RAG_NO_ANSWER_HINT, RAG_NO_ANSWER_MESSAGE } from './ragQueryCopy';

describe('ragQueryCopy (Gate 5 F1 — cause-neutral no-answer copy)', () => {
  it('states the approved neutral outcome verbatim', () => {
    expect(RAG_NO_ANSWER_MESSAGE).toBe(
      'No grounded answer was returned for this question.'
    );
  });

  it('never names a cause the response contract cannot distinguish', () => {
    const causeTerms =
      /retriev|evidence|corpus|match|provider|citation|generat|discard|fail|disabled|timeout/i;
    expect(RAG_NO_ANSWER_MESSAGE).not.toMatch(causeTerms);
    expect(RAG_NO_ANSWER_HINT).not.toMatch(causeTerms);
  });
});
