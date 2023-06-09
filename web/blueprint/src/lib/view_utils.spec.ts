import {VALUE_KEY, type LilacValueItem} from '$lilac';
import {describe, expect, it} from 'vitest';
import {mergeSpans} from './view_utils';

describe('mergeSpans', () => {
  it.only('merge one span set', () => {
    const inputSpans: {[spanSet: string]: LilacValueItem<'string_span'>[]} = {
      set1: [
        {[VALUE_KEY]: {start: 0, end: 3}, id: 0},
        {[VALUE_KEY]: {start: 4, end: 7}, id: 1},
        {[VALUE_KEY]: {start: 6, end: 10}, id: 2}
      ]
    };
    const mergedSpans = mergeSpans('0123456789extra', inputSpans);
    expect(mergedSpans).toEqual([
      {
        text: '012',
        span: {start: 0, end: 3},
        originalSpans: {set1: [inputSpans.set1[0]]}
      },
      {
        // Empty span.
        text: '3',
        span: {start: 3, end: 4},
        originalSpans: {}
      },
      {
        text: '45',
        span: {start: 4, end: 6},
        originalSpans: {set1: [inputSpans.set1[1]]}
      },
      {
        // Overlaping span.
        text: '6',
        span: {start: 6, end: 7},
        originalSpans: {set1: [inputSpans.set1[1], inputSpans.set1[2]]}
      },
      {
        text: '789',
        span: {start: 7, end: 10},
        originalSpans: {set1: [inputSpans.set1[2]]}
      },
      {
        text: 'extra',
        span: {start: 10, end: 15},
        originalSpans: {}
      }
    ]);
  });

  it.only('merge two spans', () => {
    const inputSpans: {[spanSet: string]: LilacValueItem<'string_span'>[]} = {
      set1: [
        {[VALUE_KEY]: {start: 0, end: 4}, id: 0},
        {[VALUE_KEY]: {start: 1, end: 5}, id: 1},
        {[VALUE_KEY]: {start: 7, end: 10}, id: 2}
      ],
      set2: [
        {[VALUE_KEY]: {start: 0, end: 2}, id: 3},
        {[VALUE_KEY]: {start: 8, end: 10}, id: 4}
      ]
    };
    const mergedSpans = mergeSpans('0123456789extra', inputSpans);

    expect(mergedSpans).toEqual([
      {
        text: '0',
        span: {start: 0, end: 1},
        originalSpans: {set1: [inputSpans.set1[0]], set2: [inputSpans.set2[0]]}
      },
      {
        text: '1',
        span: {start: 1, end: 2},
        originalSpans: {set1: [inputSpans.set1[0], inputSpans.set1[1]], set2: [inputSpans.set2[0]]}
      },
      {
        text: '23',
        span: {start: 2, end: 4},
        originalSpans: {set1: [inputSpans.set1[0], inputSpans.set1[1]]}
      },
      {
        text: '4',
        span: {start: 4, end: 5},
        originalSpans: {set1: [inputSpans.set1[1]]}
      },
      // Empty span.
      {text: '56', span: {start: 5, end: 7}, originalSpans: {}},
      {
        text: '7',
        span: {start: 7, end: 8},
        originalSpans: {set1: [inputSpans.set1[2]]}
      },
      {
        text: '89',
        span: {start: 8, end: 10},
        originalSpans: {set1: [inputSpans.set1[2]], set2: [inputSpans.set2[1]]}
      },
      {
        text: 'extra',
        span: {start: 10, end: 15},
        originalSpans: {}
      }
    ]);
  });
});
