import {Field, NamedBins, StatsResult} from '../../fastapi_client';
import {getEqualBins, getNamedBins, NUM_AUTO_BINS, TOO_MANY_DISTINCT} from '../db';
import {isOrdinal, isTemporal, LeafValue, Path} from '../schema';
import {
  SELECT_GROUPS_SUPPORTED_DTYPES,
  useGetStatsQuery,
  useSelectGroupsQuery,
} from '../store/apiDataset';

export interface TopKValuesResult {
  isFetching: boolean;
  values: [LeafValue, number][];
  tooManyDistinct: boolean;
  onlyTopK: boolean;
  dtypeNotSupported: boolean;
  statsResult?: StatsResult;
}

export interface TopKValuesOptions {
  namespace: string;
  datasetName: string;
  leafPath: Path;
  field: Field;
  topK: number;
  vocabOnly?: boolean;
}

/** Returns the top K values along with their counts for a given leaf.
 *
 * If the vocab is too large to compute top K, it returns null with `tooManyDistinct` set to true.
 * If the vocab is larger than top K, it returns the top K values with `onlyTopK` set to true.
 * If `vocabOnly` is true, it returns the top K values without the counts.
 */

export function useTopValues({
  namespace,
  datasetName,
  leafPath,
  field,
  topK,
  vocabOnly,
}: TopKValuesOptions): TopKValuesResult {
  const {isFetching: statsIsFetching, currentData: statsResult} = useGetStatsQuery({
    namespace,
    datasetName,
    options: {leaf_path: leafPath},
  });
  let values: [LeafValue, number][] = [];
  let skipSelectGroups = false;
  let tooManyDistinct = false;
  let dtypeNotSupported = false;
  let onlyTopK = false;
  let namedBins: NamedBins | undefined = undefined;

  // Dtype exists since the field is a leaf.
  const dtype = field.dtype!;

  if (!SELECT_GROUPS_SUPPORTED_DTYPES.includes(dtype)) {
    skipSelectGroups = true;
    dtypeNotSupported = true;
  }

  if (statsResult == null) {
    skipSelectGroups = true;
  } else if (statsResult.approx_count_distinct > TOO_MANY_DISTINCT) {
    skipSelectGroups = true;
    tooManyDistinct = true;
    onlyTopK = false;
  } else if (statsResult.approx_count_distinct > topK) {
    onlyTopK = true;
  }

  if (isOrdinal(dtype) && !isTemporal(dtype) && statsResult != null) {
    // When fetching only the vocab of a binned leaf, we can skip calling `db.select_groups()`.
    skipSelectGroups = vocabOnly ? true : false;
    tooManyDistinct = false;
    onlyTopK = false;
    const bins = getEqualBins(statsResult, leafPath, NUM_AUTO_BINS);
    namedBins = getNamedBins(bins);
  }
  const {isFetching: groupsIsFetching, currentData: groupsResult} = useSelectGroupsQuery(
    {
      namespace,
      datasetName,
      options: {leaf_path: leafPath, bins: namedBins, limit: onlyTopK ? topK : 0},
    },
    {skip: skipSelectGroups}
  );

  if (groupsResult != null) {
    values = groupsResult;
  }

  if (vocabOnly && namedBins != null) {
    values = namedBins.labels!.map((label) => [label, 0]);
  }

  return {
    isFetching: statsIsFetching || groupsIsFetching,
    values,
    tooManyDistinct,
    onlyTopK,
    dtypeNotSupported,
    statsResult,
  };
}
