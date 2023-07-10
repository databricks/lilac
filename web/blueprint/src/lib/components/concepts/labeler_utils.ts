import {L, valueAtPath, type Concept, type DataTypeCasted, type LilacValueNode} from '$lilac';

export function getCandidates(
  rows: LilacValueNode[] | undefined,
  concept: Concept,
  fieldPath: string[],
  embedding: string
) {
  if (rows == null) {
    return [];
  }
  const candidates: {text: string; score: number}[] = [];
  for (const row of rows) {
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
      if (labeledSpans.some(s => s.start === span.start && s.end === span.end)) {
        // Skip spans that are already labeled.
        continue;
      }
      const textSpan = text.slice(span.start, span.end);
      const scoreNode = valueAtPath(embNode, ['embedding', conceptId]);
      if (scoreNode == null) {
        continue;
      }
      const score = L.value(scoreNode, 'float32');
      if (score == null) {
        continue;
      }
      candidates.push({text: textSpan, score});
    }
  }
  // Sort by score, descending.
  candidates.sort((a, b) => b.score - a.score);
  const topPositive = candidates[0];
  const topNegative = candidates[candidates.length - 1];
  // Sort by distance from 0.5, ascending.
  candidates.sort((a, b) => Math.abs(a.score - 0.5) - Math.abs(b.score - 0.5));
  const res = [topPositive];
  const topNeutral = candidates.find(c => c != topPositive && c != topNegative);
  if (topNeutral != null) {
    res.push(topNeutral);
  }
  if (topNegative != topPositive) {
    res.push(topNegative);
  }
  return res;
}
