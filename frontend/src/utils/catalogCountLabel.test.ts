import { describe, expect, it } from 'vitest';
import { CATALOG_FETCH_CAP, catalogCountLabel } from './productLabel';

describe('catalogCountLabel (6C-C3)', () => {
  it('returns the exact count below the cap', () => {
    expect(catalogCountLabel(1)).toBe('1');
    expect(catalogCountLabel(20)).toBe('20');
    expect(catalogCountLabel(499)).toBe('499');
  });

  it('returns "500+" exactly at the cap', () => {
    expect(catalogCountLabel(500)).toBe('500+');
  });

  it('returns "500+" above the cap', () => {
    expect(catalogCountLabel(501)).toBe('500+');
    expect(catalogCountLabel(9999)).toBe('500+');
  });

  it('handles zero as an exact count, not a cap label', () => {
    expect(catalogCountLabel(0)).toBe('0');
  });

  it('respects a custom cap', () => {
    expect(catalogCountLabel(5, 5)).toBe('5+');
    expect(catalogCountLabel(4, 5)).toBe('4');
  });

  it('uses CATALOG_FETCH_CAP (500) as the default cap', () => {
    expect(CATALOG_FETCH_CAP).toBe(500);
    expect(catalogCountLabel(CATALOG_FETCH_CAP)).toBe('500+');
  });
});
