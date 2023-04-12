import {NamedBins, StatsResult} from '../fastapi_client';
import {Path} from './schema';
import {roundNumber} from './utils';

// Threshold for rejecting certain queries (e.g. group by) for columns with large cardinality.
export const TOO_MANY_DISTINCT = 10_000;
export const NUM_AUTO_BINS = 20;

/** Returns equally sized bins for a given field. */
export function getEqualBins(stats: StatsResult, leafPath: Path, numBins: number): number[] {
  if (stats.min_val == null || stats.max_val == null) {
    throw new Error(
      `Can not compute equal bins for leaf "${leafPath}". Missing "stats.{min|max}Val"`
    );
  }
  if (typeof stats.min_val === 'string' || typeof stats.max_val === 'string') {
    throw new Error('Can not compute equal bins for temporal fields.');
  }
  const binWidth = (stats.max_val - stats.min_val) / numBins;
  const bins: number[] = [];
  for (let i = 1; i < numBins; i++) {
    bins.push(stats.min_val + i * binWidth);
  }
  return bins;
}

export function getNamedBins(bins: number[]): NamedBins {
  const labels = [...bins, bins[bins.length - 1]].map((b, i) => {
    const num = roundNumber(b, 2).toLocaleString();
    if (i === 0) {
      return `< ${num}`;
    }
    if (i === bins.length) {
      return `≥ ${num}`;
    }
    const prevNum = roundNumber(bins[i - 1], 2).toLocaleString();
    return `${prevNum} - ${num}`;
  });
  return {bins, labels};
}
