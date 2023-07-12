import {stringSlice} from '$lib/view_utils';
import {
  L,
  UUID_COLUMN,
  valueAtPath,
  type Concept,
  type DataTypeCasted,
  type LilacValueNode
} from '$lilac';

export interface Candidate {
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
  const uuids = new Set<string>();
  const spans: {
    text: string;
    score: number;
    span: NonNullable<DataTypeCasted<'string_span'>>;
  }[] = [];
  for (const row of allRows) {
    const uuid = L.value(valueAtPath(row, [UUID_COLUMN])!, 'string');
    if (uuid == null || uuids.has(uuid)) {
      continue;
    }
    uuids.add(uuid);
    const textNode = valueAtPath(row, fieldPath);
    if (textNode == null) {
      continue;
    }
    const text = L.value(textNode, 'string');
    if (text == null) {
      continue;
    }
    const embNodes = valueAtPath(textNode, [embedding]) as unknown as LilacValueNode[];
    if (embNodes == null) {
      continue;
    }
    const conceptId = `${concept.namespace}/${concept.concept_name}`;
    const labelNodes = valueAtPath(textNode, [
      `${conceptId}/labels`
    ]) as unknown as LilacValueNode[];
    const labeledSpans: NonNullable<DataTypeCasted<'string_span'>>[] = [];
    if (labelNodes != null) {
      for (const labelNode of labelNodes) {
        const span = L.value(labelNode, 'string_span');
        if (span != null) {
          labeledSpans.push(span);
        }
      }
    }
    for (const embNode of embNodes) {
      const span = L.value(embNode, 'string_span');
      if (span == null) {
        continue;
      }

      // Skip spans that overlap with labeled pieces.
      const noOverlap = labeledSpans.every(l => l.start > span.end || l.end < span.start);
      if (!noOverlap) {
        continue;
      }

      const scoreNode = valueAtPath(embNode, ['embedding', conceptId]);
      if (scoreNode == null) {
        continue;
      }
      const score = L.value(scoreNode, 'float32');
      if (score == null) {
        continue;
      }
      spans.push({text, span, score});
    }
  }

  function spanToCandidate(span: {
    text: string;
    score: number;
    span: NonNullable<DataTypeCasted<'string_span'>>;
  }): Candidate {
    return {
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
