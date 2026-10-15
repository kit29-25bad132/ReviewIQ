import { describe, expect, it } from 'vitest';
import { estimatedMentionLabel, sampleSizeLabel } from './ProsConsAnalysis';

describe('estimatedMentionLabel (Gate 1 pros/cons truthfulness)', () => {
  it('labels extrapolated counts as estimates, never as measured counts', () => {
    const label = estimatedMentionLabel(1250, 42.3);

    expect(label).toContain('Estimated mentions');
    expect(label).toContain('~');
    expect(label).toContain('% of all reviews');
    expect(label).not.toContain('Mentioned in');
    expect(label).not.toContain('verified');
  });
});

describe('sampleSizeLabel (Gate 3 sample-vs-pool truthfulness)', () => {
  // Digit grouping differs across Node locales (e.g. 125192 renders as
  // "125,192" or "1,25,192"), so expected strings are derived with the same
  // toLocaleString the component uses.
  const n = (value: number): string => value.toLocaleString();

  it('distinguishes a valid analyzed sample from the available pool', () => {
    const label = sampleSizeLabel(5000, 125192);
    expect(label).toContain('Analyzed sample:');
    expect(label).toContain(`of ${n(125192)} available reviews`);
    // A smaller sample is never presented as the entire population.
    expect(label).not.toBe(`${n(125192)} available reviews`);
  });

  it('handles inconsistent values without claiming a subset relation', () => {
    const label = sampleSizeLabel(200, 100);
    expect(label).toContain(`Analyzed sample: ${n(200)} reviews`);
    expect(label).toContain(`available pool reported as ${n(100)}`);
    expect(label).not.toContain(`of ${n(100)}`);
  });

  it('handles a missing pool without inventing arithmetic', () => {
    const label = sampleSizeLabel(5000, null);
    expect(label).toBe(
      `Analyzed sample: ${n(5000)} reviews (available pool not reported)`
    );
  });

  it('handles a missing sample size without deriving it from the pool', () => {
    expect(sampleSizeLabel(undefined, 125192)).toBe(
      `${n(125192)} available reviews (analyzed sample size not reported)`
    );
    expect(sampleSizeLabel(null, 125192)).toBe(
      `${n(125192)} available reviews (analyzed sample size not reported)`
    );
  });

  it('handles zero and invalid values truthfully', () => {
    expect(sampleSizeLabel(0, 125192)).toBe(
      `${n(125192)} available reviews (analyzed sample size not reported)`
    );
    expect(sampleSizeLabel(5000, 0)).toBe(
      `Analyzed sample: ${n(5000)} reviews (available pool not reported)`
    );
    expect(sampleSizeLabel(Number.NaN, Number.POSITIVE_INFINITY)).toBe(
      'Sample size not reported'
    );
    expect(sampleSizeLabel(null, undefined)).toBe('Sample size not reported');
  });
});
