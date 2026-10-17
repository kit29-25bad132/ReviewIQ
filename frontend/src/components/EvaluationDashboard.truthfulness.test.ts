import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import evaluationDashboardSource from './EvaluationDashboard.tsx?raw';

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    // Effects never run during server rendering; the mocks guarantee a loud
    // failure if an evaluation call is ever moved into the render path.
    getEvaluation: vi.fn(() => Promise.resolve(null)),
    runEvaluation: vi.fn(() =>
      Promise.reject(new Error('network disabled in tests'))
    ),
  };
});

import { EvaluationDashboard } from './EvaluationDashboard';

// Gate 11 provider-claim truthfulness. Real predictions behind the metrics
// come from the configured multi-provider analysis pipeline (Gemini -> Groq ->
// OpenRouter fallback) and cached rows record no provider, so the dashboard
// must not attribute results to Gemini.
//
// Two coverage layers:
// 1. Rendered markup (effects do not run during server rendering, matching
//    the pre-effect state users see) covers the intro description, the
//    pipeline banner, and the idle run button.
// 2. A supplemental component-level static contract covers strings that only
//    exist inside the effect-gated state machine (error fallback, running
//    label, empty-state copy). The repo test setup has no DOM environment// (vitest `environment: 'node'`, no jsdom — dependencies cannot be
// installed in this gate), so those branches cannot be rendered; the
// static assertions keep them from regressing without relying on source
// search alone.
const html = renderToStaticMarkup(React.createElement(EvaluationDashboard));
const source: string = evaluationDashboardSource;

describe('EvaluationDashboard rendered truthfulness (Gate 11)', () => {
  it('attributes accuracy to the AI model, not to Gemini', () => {
    // renderToStaticMarkup HTML-escapes the apostrophe (') as &#x27;.
    expect(html).toContain('Quantify the AI model');
    expect(html).toContain(
      's predicted rating and sentiment accuracy against real ground-truth Amazon reviews.'
    );
    expect(html).not.toContain('Gemini&#x27;s predicted');
    expect(html).not.toContain("Gemini's predicted");
  });

  it('describes the pipeline as AI structured output', () => {
    expect(html).toContain('Evaluates dataset reviews through AI structured output.');
    expect(html).not.toContain('Gemini AI structured output');
  });

  it('renders no unqualified provider claim in the initial markup', () => {
    expect(html).not.toContain('Gemini');
    expect(html).not.toContain('Groq');
    expect(html).not.toContain('OpenRouter');
  });

  it('preserves accurate ground-truth and control copy', () => {
    // '&' is HTML-escaped by renderToStaticMarkup, so assert the plain prefix.
    expect(html).toContain('AI Model Evaluation ');
    expect(html).toContain('Run AI Evaluation');
    expect(html).toContain('Force Re-analyze');
    expect(html).toContain('ground-truth Amazon reviews');
  });
});

describe('EvaluationDashboard effect-gated strings (Gate 11 static contract)', () => {
  it('falls back to a provider-neutral evaluation error message', () => {
    expect(source).toContain(
      'Failed to run evaluation. Please check the backend configuration and try again.'
    );
    expect(source).not.toContain('verify Gemini API key');
    expect(source).not.toContain('Gemini API key');
  });

  it('uses a provider-neutral running label', () => {
    expect(source).toContain('<span>Evaluating...</span>');
    expect(source).not.toContain('Evaluating with Gemini');
  });

  it('identifies the benchmark dataset the frontend actually queries', () => {
    expect(source).toContain(
      'to benchmark the AI analysis pipeline on a sample of benchmark dataset reviews.'
    );
    // The frontend omits the `source` parameter, so runs default to the
    // benchmark CSV — asserting "canonical" here would be factually wrong.
    expect(source).not.toContain('canonical dataset reviews');
  });

  it('makes no provider-specific claim anywhere in the rendered component source', () => {
    expect(source).not.toContain('Gemini');
    expect(source).not.toContain('Groq');
    expect(source).not.toContain('OpenRouter');
  });
});