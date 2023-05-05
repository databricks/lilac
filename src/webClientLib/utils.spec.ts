import { describe, expect, it } from 'vitest';
import { mergeDeep } from './utils';

describe('utils', () => {
  describe('mergeDeep', () => {
    it('should merge two objects', () => {
      expect(mergeDeep({ a: 1, b: 2 }, { c: 3 })).toEqual({ a: 1, b: 2, c: 3 });
      expect(mergeDeep({ a: { b: { c: 1 } } }, { a: { b: { d: 2 } } })).toEqual({
        a: {
          b: {
            c: 1,
            d: 2
          }
        }
      });
    });

    it('shouldnt overwrite existing values', () => {
      expect(mergeDeep({ a: 1, b: 2, c: 4 }, { c: 3 })).toEqual({ a: 1, b: 2, c: 4 });
    });
  });
});
