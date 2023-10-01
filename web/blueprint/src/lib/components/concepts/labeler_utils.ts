import {stringSlice} from '$lib/view_utils';
import {
  L,
  ROWID,
  valueAtPath,
  type Concept,
  type DataTypeCasted,
  type LilacValueNode
} from '$lilac';

export interface Candidate {
  rowid: string;
  text: string;
  score: number;
  label?: boolean;
}

export interface Candidates {
  positive?: Candidate;
  neutral?: Candidate;
  negative?: Candidate;
}

export function getCandidates(
  prevCandidates: Candidates,
  topRows: LilacValueNode[] | undefined,
  randomRows: LilacValueNode[] | undefined,
  concept: Concept,
  fieldPath: string[],
  embedding: string
): Candidates {
  const candidates: Candidates = {...prevCandidates};
  if (topRows == null || randomRows == null) {
    return candidates;
  }
  const allRows = [...topRows, ...randomRows];
  const rowids = new Set<string>();
  const spans: {
    rowid: string;
    text: string;
    score: number;
    span: NonNullable<DataTypeCasted<'string_span'>>;
  }[] = [];
  for (const row of allRows) {
    const rowid = L.value(valueAtPath(row, [ROWID])!, 'string');
    if (rowid == null || rowids.has(rowid)) {
      continue;
    }
    rowids.add(rowid);
    const textNode = valueAtPath(row, fieldPath);
    if (textNode == null) {
      continue;
    }
    const text = L.value(textNode, 'string');
    if (text == null) {
      continue;
    }
    const conceptId = `${concept.namespace}/${concept.concept_name}`;
    const spanNodes = valueAtPath(textNode, [
      `${conceptId}/${embedding}`
    ]) as unknown as LilacValueNode[];
    if (spanNodes == null) {
      continue;
    }

    const labelNodes = valueAtPath(textNode, [
      `${conceptId}/labels`
    ]) as unknown as LilacValueNode[];
    const labeledSpans: NonNullable<DataTypeCasted<'string_span'>>[] = [];
    if (labelNodes != null) {
      for (const labelNode of labelNodes) {
        const span = L.span(labelNode);
        if (span != null) {
          labeledSpans.push(span);
        }
      }
    }
    for (const spanNode of spanNodes) {
      const span = L.span(spanNode);
      if (span == null) {
        continue;
      }

      // Skip spans that overlap with labeled pieces.
      const noOverlap = labeledSpans.every(l => l.start > span.end || l.end < span.start);
      if (!noOverlap) {
        continue;
      }

      const scoreNode = valueAtPath(spanNode, ['score']);
      if (scoreNode == null) {
        continue;
      }
      const score = L.value(scoreNode, 'float32');
      if (score == null) {
        continue;
      }
      spans.push({rowid, text, span, score});
    }
  }

  function spanToCandidate(span: {
    rowid: string;
    text: string;
    score: number;
    span: NonNullable<DataTypeCasted<'string_span'>>;
  }): Candidate {
    return {
      rowid: span.rowid,
      text: stringSlice(span.text, span.span.start, span.span.end),
      score: span.score
    };
  }

  // Sort by score, descending.
  spans.sort((a, b) => b.score - a.score);
  const positive = spans[0];
  const negative = spans
    .slice()
    .reverse()
    .find(s => s != positive);
  // Sort by distance from 0.5, ascending.
  spans.sort((a, b) => Math.abs(a.score - 0.5) - Math.abs(b.score - 0.5));
  const neutral = spans.find(s => s != positive && s != negative);

  if (positive != null && candidates.positive == null) {
    candidates.positive = spanToCandidate(positive);
  }
  if (neutral != null && candidates.neutral == null) {
    candidates.neutral = spanToCandidate(neutral);
  }
  if (negative != null && candidates.negative == null) {
    candidates.negative = spanToCandidate(negative);
  }
  return candidates;
}
