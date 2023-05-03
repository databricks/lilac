import {Filter} from '../../fastapi_client';
import {Item, UUID_COLUMN} from '../schema';
import {useSelectRowsQuery} from '../store/apiDataset';

/** Fetches the data associated with an item from the dataset. */
export function useGetItem(args: {namespace: string; datasetName: string; itemId: string}): {
  isFetching: boolean;
  item: Item | null;
  error?: unknown;
} {
  const {namespace, datasetName, itemId} = args;
  const filters: Filter[] = [{path: [UUID_COLUMN], comparison: 'equals', value: itemId}];
  const {
    isFetching,
    currentData: items,
    error,
  } = useSelectRowsQuery({namespace, datasetName, options: {filters, limit: 1}});

  const item = items?.[0] ?? null;

  return {isFetching, item, error};
}
