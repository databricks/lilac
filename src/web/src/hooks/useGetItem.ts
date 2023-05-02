import {Item} from '../schema';
import {useSelectRowsByUUIDQuery} from '../store/apiDataset';

/** Fetches the data associated with an item from the dataset. */
export function useGetItem(args: {namespace: string; datasetName: string; itemId: string}): {
  isFetching: boolean;
  item: Item | null;
  error?: unknown;
} {
  const {namespace, datasetName, itemId} = args;
  const {isFetching, currentData, error} = useSelectRowsByUUIDQuery({
    namespace,
    datasetName,
    options: {},
    uuid: itemId,
  });

  return {isFetching, item: currentData ?? null, error};
}
