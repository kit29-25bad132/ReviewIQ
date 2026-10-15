import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    // Effects never run during server rendering; the mock guarantees a loud
    // failure if a call is ever moved into the render path.
    generateAISummary: vi.fn(() =>
      Promise.reject(new Error('network disabled in tests'))
    ),
  };
});

import {
  AISummaryCard,
  extractSummaryErrorMessage,
  isEmptySummaryState,
} from './AISummaryCard';

describe('extractSummaryErrorMessage (Gate 3)', () => {
  it('uses the safe server-provided detail on HTTP 500', () => {
    const err = {
      response: {
        data: {
          detail:
            'Connection to AI service timed out or unavailable. Please verify your network connection.',
        },
      },
    };
    expect(extractSummaryErrorMessage(err)).toBe(
      'Connection to AI service timed out or unavailable. Please verify your network connection.'
    );
  });

  it('uses the safe server-provided detail on HTTP 400', () => {
    const err = {
      response: { data: { detail: 'AI summary failed validation. Please try again.' } },
    };
    expect(extractSummaryErrorMessage(err)).toBe(
      'AI summary failed validation. Please try again.'
    );
  });

  it('falls back to a concise generic message on network failure (no response)', () => {
    const message = extractSummaryErrorMessage(new Error('Network Error'));
    expect(message).toBe('Unable to generate an AI summary right now. Please try again.');
  });

  it('ignores missing, empty, or non-string detail values', () => {
    const generic = 'Unable to generate an AI summary right now. Please try again.';
    expect(extractSummaryErrorMessage({ response: {} })).toBe(generic);
    expect(extractSummaryErrorMessage({ response: { data: {} } })).toBe(generic);
    expect(extractSummaryErrorMessage({ response: { data: { detail: '' } } })).toBe(generic);
    expect(extractSummaryErrorMessage({ response: { data: { detail: '   ' } } })).toBe(generic);
    expect(extractSummaryErrorMessage({ response: { data: { detail: { obj: true } } } })).toBe(
      generic
    );
    expect(extractSummaryErrorMessage(undefined)).toBe(generic);
    expect(extractSummaryErrorMessage('plain string failure')).toBe(generic);
  });

  it('never renders raw exception objects or sensitive canary text', () => {
    const canary = 'sk-live-canary-123 internals=/var/log/x';
    const err = Object.assign(new Error(canary), {
      response: { data: { detail: 'AI analysis is unavailable. Please check the server configuration.' } },
    });
    const message = extractSummaryErrorMessage(err);
    expect(message).not.toContain(canary);
    expect(message).not.toContain('sk-live');
    expect(message).not.toContain('Error:');
    expect(message).not.toContain('[object Object]');
  });
});

describe('isEmptySummaryState (Gate 3)', () => {
  it('detects the explicit backend empty state', () => {
    expect(
      isEmptySummaryState({
        summary: 'No customer reviews are available in the dataset for this product.',
      })
    ).toBe(true);
  });

  it('does not treat a generated summary as an empty state', () => {
    expect(
      isEmptySummaryState({ summary: 'Customers like the clean design and long battery.' })
    ).toBe(false);
  });
});

describe('AISummaryCard initial render (Gate 3)', () => {
  const html = renderToStaticMarkup(
    React.createElement(AISummaryCard, { productId: '9640962' })
  );

  it('shows the not-generated state, not a fabricated or stale summary', () => {
    expect(html).toContain('No AI summary generated yet for this product.');
    expect(html).not.toContain('No customer reviews are available');
  });

  it('does not claim AI generation before any summary exists (Gate 4)', () => {
    expect(html).not.toContain('AI-generated');
    expect(html).not.toContain('constrained strictly to dataset reviews');
  });

  it('keeps provider wording neutral', () => {
    expect(html).not.toContain('Gemini');
  });
});
