import {describe, expect, it} from 'vitest';
import {VALUE_KEY} from './schema';
import {mergeDeep, mergeSpans} from './utils';

describe('utils', () => {
  describe('mergeDeep', () => {
    it('should merge two objects', () => {
      expect(mergeDeep({a: 1, b: 2}, {c: 3})).toEqual({a: 1, b: 2, c: 3});
      expect(mergeDeep({a: {b: {c: 1}}}, {a: {b: {d: 2}}})).toEqual({
        a: {
          b: {
            c: 1,
            d: 2
          }
        }
      });
    });

    it('shouldnt overwrite existing values', () => {
      expect(mergeDeep({a: 1, b: 2, c: 4}, {c: 3})).toEqual({a: 1, b: 2, c: 4});
    });
  });

  describe.only('mergeSpans', () => {
    it('merge two spans', () => {
      const inputSpans = [
        [
          {[VALUE_KEY]: {start: 0, end: 4}, id: 0},
          {[VALUE_KEY]: {start: 6, end: 10}, id: 1}
        ],
        [
          {[VALUE_KEY]: {start: 0, end: 2}, id: 2},
          {[VALUE_KEY]: {start: 8, end: 10}, id: 3}
        ]
      ];
      const mergedSpans = mergeSpans('0123456789extra', inputSpans);

      expect(mergedSpans).toEqual([
        {
          text: '01',
          span: {start: 0, end: 2},
          originalSpans: [inputSpans[0][0], inputSpans[1][0]]
        },
        {
          text: '23',
          span: {start: 2, end: 4},
          originalSpans: [inputSpans[0][0]]
        },
        // Empty span.
        {text: '45', span: {start: 4, end: 6}, originalSpans: []},
        {
          text: '67',
          span: {start: 6, end: 8},
          originalSpans: [inputSpans[0][1]]
        },
        {
          text: '89',
          span: {start: 8, end: 10},
          originalSpans: [inputSpans[0][1], inputSpans[1][1]]
        },
        {
          text: 'extra',
          span: {start: 10, end: 15},
          originalSpans: []
        }
      ]);
    });
  });
});
