import React from 'react';
import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

// The ProsConsAnalysis component this file originally covered was
// intentionally removed by Phase 5 and replaced by the evidence-backed
// intelligence surface: AspectThemes for recurring-theme mention counts and
// GroundedClaims for pros/cons. Phase 5 counts are measured over the whole
// product corpus (no sample projection reaches the UI), so the Gate 1/Gate 3
// truthfulness assertions below exercise the replacement components.
import { AspectThemes } from './AspectThemes';
import { GroundedClaims } from './GroundedClaims';
import type { AspectResult, ClaimWithEvidence } from '../types/intelligence';

describe('AspectThemes mention counts (Gate 1 pros/cons truthfulness)', () => {
  const aspects: AspectResult[] = [
    {
      aspect_name: 'battery life',
      sentiment: 'positive',
      mention_count: 42,
      representative_quote: { review_id: 'R-7', excerpt: 'Battery lasts two days.' },
    },
  ];
  const html = renderToStaticMarkup(React.createElement(AspectThemes, { aspects }));

  it('renders theme mentions as the measured count reported by the backend', () => {
    expect(html).toContain('Mentioned in 42 reviews');
    // Legacy extrapolated wording must never reappear: counts shown here are
    // counted over the real corpus, never projected from a sample.
    expect(html).not.toContain('% of all reviews');
    expect(html).not.toContain('Estimated mentions');
  });

  it('attributes every theme to a real review citation', () => {
    expect(html).toContain('Battery lasts two days.');
    expect(html).toContain('[R-7]');
  });

  it('renders no themes at all when the backend found none (no fabricated fallback)', () => {
    const empty = renderToStaticMarkup(React.createElement(AspectThemes, { aspects: [] }));
    expect(empty).toBe('');
    expect(empty).not.toContain('High Price Tag');
    expect(empty).not.toContain('Mentioned in');
  });

  it('uses singular wording for a single real mention', () => {
    const single = renderToStaticMarkup(
      React.createElement(AspectThemes, {
        aspects: [
          {
            aspect_name: 'screen',
            sentiment: 'mixed',
            mention_count: 1,
            representative_quote: { review_id: 'R-1', excerpt: 'Bright screen.' },
          },
        ],
      })
    );
    expect(single).toContain('Mentioned in 1 review');
    expect(single).not.toContain('Mentioned in 1 reviews');
  });
});

describe('GroundedClaims evidence (Gate 1/Gate 3)', () => {
  const pros: ClaimWithEvidence[] = [
    {
      claim: 'Battery life is praised',
      support_count: 3,
      evidence: [
        { review_id: 'R-1', excerpt: 'Battery lasts two days.' },
        { review_id: 'R-2', excerpt: 'Charge lasts a week.' },
      ],
    },
  ];

  const html = renderToStaticMarkup(
    React.createElement(GroundedClaims, { pros, cons: [] })
  );

  it('labels support with the real number of citing reviews and shows the citations', () => {
    expect(html).toContain('Supported by 3 reviews');
    expect(html).toContain('Battery lasts two days.');
    expect(html).not.toContain('verified');
  });

  it('keeps an explicit empty state instead of inventing cons', () => {
    expect(html).toContain('No evidence-backed cons found in these reviews.');
    expect(html).not.toContain('High Price Tag');
  });

  it('keeps an explicit empty state instead of inventing pros', () => {
    const empty = renderToStaticMarkup(
      React.createElement(GroundedClaims, { pros: [], cons: [] })
    );
    expect(empty).toContain('No evidence-backed pros found in these reviews.');
    expect(empty).toContain('No evidence-backed cons found in these reviews.');
    expect(empty).not.toContain('High Price Tag');
    expect(empty).not.toContain('verified');
  });
});
