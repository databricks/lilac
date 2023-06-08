import type {LilacValueItem} from './lilac';
import {VALUE_KEY, type DataTypeCasted} from './schema';

export function isObject(item: unknown): item is Record<string, unknown> {
  return item && typeof item === 'object' && !Array.isArray(item) ? true : false;
}

export function mergeDeep<T>(target: T, ...sources: T[]): T {
  if (!sources.length) return target;
  const source = sources.shift();

  if (isObject(target) && isObject(source)) {
    for (const key in source) {
      const t = target[key];
      const s = source[key];
      if (isObject(s) && isObject(t)) {
        if (!t) Object.assign(target, {[key]: {}});
        mergeDeep(t, s);
      } else if (!t) {
        Object.assign(target, {[key]: s});
      }
    }
  }
  return mergeDeep(target, ...sources);
}

export interface RenderSpan {
  text: string;
  span: DataTypeCasted<'string_span'>;
  originalSpans: LilacValueItem<'string_span'>[];
}
/**
 * Merge a set of spans on a single item into a single list of spans, each with points back to
 * the original spans.
 *
 * For example:
 *   spans1: [(0, 2), (3, 4)]
 *   spans2: [(0, 1), (2, 4)]
 * Transforms into:
 *   spans: [(0, 1, (span1,span2)),
 *           (1, 2, (span1)),
 *           (2, 3, (span2)),
 *           (3, 4, (span4))]
 */
export function mergeSpans(
  text: string,
  inputSpanSets: LilacValueItem<'string_span'>[][]
): RenderSpan[] {
  // Maps a span set to the index of the span we're currently processing. The size of this array is
  // the size of the number of span sets we're computing over (small).
  const spanSetIndices: (number | null)[] = Array(inputSpanSets.length).fill(0);

  let curStartIdx = 0;
  const renderSpans: RenderSpan[] = [];
  let spanSetWorkingSpans = spanSetIndices.map((spanId, spanSetIdx) =>
    spanId != null ? inputSpanSets[spanSetIdx][spanId] : null
  );
  while (spanSetWorkingSpans.some(i => i != null)) {
    // Compute the next end index.
    let curEndIndex = Infinity;
    for (let i = 0; i < spanSetWorkingSpans.length; i++) {
      const span = (spanSetWorkingSpans[i] || {})[VALUE_KEY];
      if (span == null) continue;
      if (span.start < curEndIndex && span.start > curStartIdx) {
        curEndIndex = span.start;
      }
      if (span.end < curEndIndex && span.end > curStartIdx) {
        curEndIndex = span.end;
      }
    }

    // Filter the spans that meet the range.
    const spansInRange = spanSetWorkingSpans.filter(
      x =>
        x != null &&
        x[VALUE_KEY] != null &&
        x[VALUE_KEY].start < curEndIndex &&
        x[VALUE_KEY].end >= curStartIdx
    ) as LilacValueItem<'string_span'>[];

    renderSpans.push({
      text: text.slice(curStartIdx, curEndIndex),
      span: {start: curStartIdx, end: curEndIndex},
      originalSpans: spansInRange
    });

    // Advance the spans that have the span end index.
    for (let i = 0; i < spanSetWorkingSpans.length; i++) {
      const span = spanSetWorkingSpans[i];
      const spanSetIdx = spanSetIndices[i];
      if (span == null || spanSetIdx == null) continue;
      if (span[VALUE_KEY]?.end === curEndIndex) {
        spanSetIndices[i] = spanSetIdx > inputSpanSets[i].length ? null : spanSetIdx + 1;
      }
    }

    curStartIdx = curEndIndex;
    spanSetWorkingSpans = spanSetIndices.map((spanId, spanSetIdx) =>
      spanId != null ? inputSpanSets[spanSetIdx][spanId] : null
    );
  }

  // If the text has more characters than spans, emit a final empty span.
  if (curStartIdx < text.length) {
    renderSpans.push({
      text: text.slice(curStartIdx, text.length),
      span: {start: curStartIdx, end: text.length},
      originalSpans: []
    });
  }

  return renderSpans;
}
