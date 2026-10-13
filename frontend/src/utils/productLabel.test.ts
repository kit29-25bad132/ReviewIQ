import { describe, expect, it } from 'vitest';
import { productLabel } from './productLabel';

describe('productLabel (6C-C1)', () => {
  it('uses a normal product name as the primary label and keeps the ID', () => {
    expect(productLabel({ asin: 'P03', product_name: 'Orbix M14' })).toEqual({
      name: 'Orbix M14',
      id: 'P03',
    });
  });

  it('falls back to the ID when product_name is missing (null/undefined)', () => {
    expect(productLabel({ asin: 'P12', product_name: null })).toEqual({
      name: 'P12',
      id: 'P12',
    });
    expect(productLabel({ asin: 'P12' })).toEqual({ name: 'P12', id: 'P12' });
  });

  it('falls back to the ID when product_name is empty', () => {
    expect(productLabel({ asin: 'P07', product_name: '' })).toEqual({
      name: 'P07',
      id: 'P07',
    });
  });

  it('falls back to the ID when product_name is whitespace-only', () => {
    expect(productLabel({ asin: 'P10', product_name: '   ' })).toEqual({
      name: 'P10',
      id: 'P10',
    });
    expect(productLabel({ asin: 'P10', product_name: '\t\n ' })).toEqual({
      name: 'P10',
      id: 'P10',
    });
  });

  it('never returns the literal "Product" placeholder', () => {
    expect(productLabel({ asin: 'P01', product_name: '' }).name).not.toBe('Product');
    expect(productLabel({ asin: null, product_name: null }).name).not.toBe('Product');
  });

  it('returns an empty name only when both fields are unusable', () => {
    expect(productLabel({ asin: null, product_name: null })).toEqual({
      name: '',
      id: null,
    });
    expect(productLabel({ asin: '  ', product_name: '' })).toEqual({
      name: '',
      id: null,
    });
  });
});
