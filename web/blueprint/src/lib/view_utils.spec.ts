import {PATH_KEY, SPAN_KEY, type LilacValueNodeCasted} from '$lilac';
import {describe, expect, it} from 'vitest';
import {mergeSpans} from './view_utils';

describe('mergeSpans', () => {
  it('merge one span set', () => {
    const inputSpans: {[spanSet: string]: LilacValueNodeCasted<'string_span'>[]} = {
      set1: [
        {id: 0, [SPAN_KEY]: {start: 0, end: 3}, [PATH_KEY]: ['0']},
        {id: 1, [SPAN_KEY]: {start: 4, end: 7}, [PATH_KEY]: ['1']},
        {id: 2, [SPAN_KEY]: {start: 6, end: 10}, [PATH_KEY]: ['2']}
      ]
    };
    const mergedSpans = mergeSpans('0123456789extra', inputSpans);
    expect(mergedSpans).toEqual([
      {
        text: '012',
        span: {start: 0, end: 3},
        originalSpans: {set1: [inputSpans.set1[0]]},
        paths: ['0']
      },
      {
        // Empty span.
        text: '3',
        span: {start: 3, end: 4},
        originalSpans: {},
        paths: []
      },
      {
        text: '45',
        span: {start: 4, end: 6},
        originalSpans: {set1: [inputSpans.set1[1]]},
        paths: ['1']
      },
      {
        // Overlaping span.
        text: '6',
        span: {start: 6, end: 7},
        originalSpans: {set1: [inputSpans.set1[1], inputSpans.set1[2]]},
        paths: ['1', '2']
      },
      {
        text: '789',
        span: {start: 7, end: 10},
        originalSpans: {set1: [inputSpans.set1[2]]},
        paths: ['2']
      },
      {
        text: 'extra',
        span: {start: 10, end: 15},
        originalSpans: {},
        paths: []
      }
    ]);
  });

  it('merge two spans', () => {
    const inputSpans: {[spanSet: string]: LilacValueNodeCasted<'string_span'>[]} = {
      set1: [
        {
          id: 0,
          [SPAN_KEY]: {start: 0, end: 4},
          [PATH_KEY]: ['0', '0']
        },
        {id: 1, [SPAN_KEY]: {start: 1, end: 5}, [PATH_KEY]: ['0', '1']},
        {id: 2, [SPAN_KEY]: {start: 7, end: 10}, [PATH_KEY]: ['0', '2']}
      ],
      set2: [
        {id: 3, [SPAN_KEY]: {start: 0, end: 2}, [PATH_KEY]: ['1', '0']},
        {id: 4, [SPAN_KEY]: {start: 8, end: 10}, [PATH_KEY]: ['1', '1']}
      ]
    };
    const mergedSpans = mergeSpans('0123456789extra', inputSpans);

    expect(mergedSpans).toEqual([
      {
        text: '0',
        span: {start: 0, end: 1},
        originalSpans: {set1: [inputSpans.set1[0]], set2: [inputSpans.set2[0]]},
        paths: ['0.0', '1.0']
      },
      {
        text: '1',
        span: {start: 1, end: 2},
        originalSpans: {set1: [inputSpans.set1[0], inputSpans.set1[1]], set2: [inputSpans.set2[0]]},
        paths: ['0.0', '0.1', '1.0']
      },
      {
        text: '23',
        span: {start: 2, end: 4},
        originalSpans: {set1: [inputSpans.set1[0], inputSpans.set1[1]]},
        paths: ['0.0', '0.1']
      },
      {
        text: '4',
        span: {start: 4, end: 5},
        originalSpans: {set1: [inputSpans.set1[1]]},
        paths: ['0.1']
      },
      // Empty span.
      {text: '56', span: {start: 5, end: 7}, originalSpans: {}, paths: []},
      {
        text: '7',
        span: {start: 7, end: 8},
        originalSpans: {set1: [inputSpans.set1[2]]},
        paths: ['0.2']
      },
      {
        text: '89',
        span: {start: 8, end: 10},
        originalSpans: {set1: [inputSpans.set1[2]], set2: [inputSpans.set2[1]]},
        paths: ['0.2', '1.1']
      },
      {
        text: 'extra',
        span: {start: 10, end: 15},
        originalSpans: {},
        paths: []
      }
    ]);
  });
});
