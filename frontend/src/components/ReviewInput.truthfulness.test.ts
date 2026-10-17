import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

import { ReviewInput } from './ReviewInput';

// Gate 11 provider-claim truthfulness: the raw-review action runs through a
// configured multi-provider fallback chain (and even a local frontend
// heuristic on timeout), so the UI must never assert that Gemini is the
// serving provider. Rendering covers both states reachable through props:
// idle (description) and loading (progress label). Effects are irrelevant
// here, so server rendering exercises the real user-visible markup.

const noop = () => undefined;

const renderReviewInput = (isLoading: boolean): string =>
  renderToStaticMarkup(
    React.createElement(ReviewInput, {
      onAnalyze: vi.fn(async () => {
        // no network in tests; the component only awaits this callback
      }),
      isLoading,
      errorMessage: null,
      onClearError: noop,
    })
  );

describe('ReviewInput provider-claim truthfulness (Gate 11)', () => {
  const idleHtml = renderReviewInput(false);
  const loadingHtml = renderReviewInput(true);

  it('describes the analysis as using AI, not a specific provider', () => {
    expect(idleHtml).toContain(
      'Paste raw text feedback to extract structured insights, pros, cons, and ratings using AI.'
    );
    expect(idleHtml).not.toContain('using Gemini AI');
  });

  it('uses a provider-neutral progress label while analyzing', () => {
    expect(loadingHtml).toContain('Analyzing review...');
    expect(loadingHtml).not.toContain('Analyzing with Gemini');
  });

  it('makes no unqualified provider claim in any rendered state', () => {
    for (const html of [idleHtml, loadingHtml]) {
      expect(html).not.toContain('Gemini');
      expect(html).not.toContain('Groq');
      expect(html).not.toContain('OpenRouter');
    }
  });

  it('preserves the surrounding copy and submit behavior', () => {
    expect(idleHtml).toContain('Direct Review AI Analyzer');
    expect(idleHtml).toContain('Analyze Review');
    expect(idleHtml).toContain('Try Sample Review');
    expect(idleHtml).toMatch(/0 \/ 5,?000 chars/);
    // Loading state keeps the same button slot, just with neutral copy.
    expect(loadingHtml).toContain('animate-spin');
  });
});