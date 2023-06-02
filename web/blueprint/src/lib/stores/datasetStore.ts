/** The store for runtime information about the dataset, like the schema and stats. */
import type {LilacSchema, Path, StatsResult} from '$lilac';
import type {QueryObserverResult} from '@tanstack/svelte-query';
import {getContext, hasContext, setContext} from 'svelte';
import type {Readable, Writable} from 'svelte/store';

const DATASET_INFO_CONTEXT = 'DATASET_INFO_CONTEXT';

export interface DatasetStore {
  schema: LilacSchema | null;
  stats: StatsInfo[] | null;
}
export interface StatsInfo {
  path: Path;
  stats: QueryObserverResult<StatsResult, unknown>;
}

export function setDatasetContext(stats: Writable<DatasetStore>) {
  setContext(DATASET_INFO_CONTEXT, stats);
}

export function getDatasetContext() {
  if (!hasContext(DATASET_INFO_CONTEXT)) return null;
  return getContext<Readable<DatasetStore>>(DATASET_INFO_CONTEXT);
}
