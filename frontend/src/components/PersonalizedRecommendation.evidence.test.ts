import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    // Effects never run during server rendering; the mock guarantees a loud
    // failure if a call is ever moved into the render path.
    getPersonalizedRecommendation: vi.fn(() =>
      Promise.reject(new Error('network disabled in tests'))
    ),
  };
});

import { PersonalizedRecommendation, evidenceTone } from './PersonalizedRecommendation';

describe('evidenceTone (Gate 3)', () => {
  it('gives the positive treatment only to the documented strong value', () => {
    expect(evidenceTone('Strong Evidence')).toBe('strong');
  });

  it('renders "No Direct Evidence" as a neutral state', () => {
    expect(evidenceTone('No Direct Evidence')).toBe('neutral');
  });

  it('never promotes unknown or missing values to the positive state', () => {
    expect(evidenceTone('Moderate Evidence')).toBe('neutral');
    expect(evidenceTone('Verified')).toBe('neutral');
    expect(evidenceTone('')).toBe('neutral');
    expect(evidenceTone(null)).toBe('neutral');
    expect(evidenceTone(undefined)).toBe('neutral');
    expect(evidenceTone('STRONG EVIDENCE')).toBe('neutral');
  });
});

describe('PersonalizedRecommendation initial render (Gate 3)', () => {
  const html = renderToStaticMarkup(
    React.createElement(PersonalizedRecommendation, {
      productId: '9640962',
      productTitle: 'Test Product',
    })
  );

  it('shows the loading state without any fabricated evidence or verdict', () => {
    expect(html).toContain('Comparing category alternatives');
    expect(html).not.toContain('Strong Evidence');
    expect(html).not.toContain('No Direct Evidence');
  });

  it('does not claim evidence is verified and stays provider-neutral', () => {
    expect(html).not.toContain('verified');
    expect(html).not.toContain('Gemini');
  });
});
