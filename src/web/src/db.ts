import {StatsResult} from '../fastapi_client';
import {Path} from './schema';

// Threshold for rejecting certain queries (e.g. group by) for columns with large cardinality.
export const TOO_MANY_DISTINCT = 100_000;

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
