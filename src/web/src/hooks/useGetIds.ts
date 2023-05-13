import {Column, ConceptScoreSignal, Filter, SortOrder} from '../../fastapi_client';
import {Path, UUID_COLUMN} from '../schema';
import {useSelectRowsQuery} from '../store/apiDataset';
import {ActiveConceptState} from '../store/store';
import {getConceptAlias} from '../utils';

/** Fetches a set of ids from the dataset that satisfy the specified filters. */
export function useGetIds(args: {
  namespace: string;
  datasetName: string;
  filters: Filter[];
  activeConcept?: ActiveConceptState | null | undefined;
  limit: number;
  offset: number;
  sortBy?: Path[];
  sortOrder?: SortOrder;
}): {isFetching: boolean; ids: string[] | null; error?: unknown} {
  const {namespace, datasetName, filters, activeConcept, limit, offset, sortOrder} = args;
  let {sortBy} = args;

  /** Always select the UUID column and sort by column. */
  let columns: (Column | string[])[] = [[UUID_COLUMN]];
  if (sortBy != null) {
    columns = [...columns, ...sortBy];
  }
  // If there is an active concept, add it to the selected columns.
  if (activeConcept != null) {
    const signal: ConceptScoreSignal = {
      signal_name: 'concept_score',
      namespace: activeConcept.concept.namespace,
      concept_name: activeConcept.concept.name,
      embedding_name: activeConcept.embedding.name,
    };
    const alias = getConceptAlias(
      activeConcept.concept,
      activeConcept.column,
      activeConcept.embedding
    );
    const conceptColumn: Column = {path: activeConcept.column, signal_udf: signal, alias};
    columns = [...columns, conceptColumn];
    // If no sort is specified, sort by the active concept.
    if (sortBy == null) {
      sortBy = [[alias]];
    }
  }
  const {
    isFetching,
    currentData: items,
    error,
  } = useSelectRowsQuery({
    namespace,
    datasetName,
    options: {
      filters,
      columns,
      limit,
      offset,
      sort_by: sortBy,
      sort_order: sortOrder,
    },
  });
  let ids: string[] | null = null;
  if (items) {
    ids = items.map((item) => item[UUID_COLUMN] as string);
  }
  return {isFetching, ids, error};
}
