import type { Path } from '$lib/schema';
import { writable } from 'svelte/store';

const createDatasetViewStore = () => {
  const { subscribe, set, update } = writable<{
    visibleColumns: Path[];
  }>({
    visibleColumns: []
  });

  return {
    subscribe,
    set,
    update,
    addVisibleColumn: (column: Path) =>
      update((state) => {
        state.visibleColumns.push(column);
        return state;
      }),
    removeVisibleColumn: (column: Path) =>
      update((state) => {
        state.visibleColumns = state.visibleColumns.filter((c) => c.join('.') !== column.join('.'));
        return state;
      })
  };
};
export const datasetViewStore = createDatasetViewStore();
