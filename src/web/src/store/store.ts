/**
 * The global application redux state store.
 */
import {
  combineReducers,
  configureStore,
  createSlice,
  isRejectedWithValue,
  Middleware,
  PayloadAction,
  PreloadedState,
} from '@reduxjs/toolkit';
import {createApi} from '@reduxjs/toolkit/query/react';
import {createRoot} from 'react-dom/client';
import {
  Column,
  ConceptInfo,
  ConceptScoreSignal,
  EmbeddingInfo,
  Field,
  Filter,
  NamedBins,
  SignalTransform,
  SortOrder,
  StatsResult,
  TaskManifest,
  TasksService,
} from '../../fastapi_client';
import {getEqualBins, getNamedBins, NUM_AUTO_BINS, TOO_MANY_DISTINCT} from '../db';
import {isOrdinal, isTemporal, Item, LeafValue, Path, UUID_COLUMN} from '../schema';

import {useParams} from 'react-router-dom';
import {useAppSelector} from '../hooks';
import {SearchBoxPage} from '../search_box/search_box';
import {getConceptAlias, renderError} from '../utils';
import {conceptApi} from './api_concept';
import {
  datasetApi,
  SELECT_GROUPS_SUPPORTED_DTYPES,
  useGetStatsQuery,
  useSelectGroupsQuery,
  useSelectRowsQuery,
} from './api_dataset';
import {embeddingApi} from './api_embeddings';
import {signalApi} from './api_signal';
import {fastAPIBaseQuery} from './api_utils';

interface ActiveConceptState {
  concept: ConceptInfo;
  column: Path;
  embedding: EmbeddingInfo;
}

interface DatasetState {
  // The active global concept. This is set when a column is actively being edited.
  activeConcept?: ActiveConceptState | null;

  browser: {
    // Selects.
    /** A list of paths to preview as "media" in the gallery item. */
    selectedMediaPaths?: Path[];
    /** A list of paths to preview as metadata (non-media) in the gallery item .*/
    selectedMetadataPaths?: Path[];

    // Filters.

    // Order.
    sort?: {
      /** The column to sort by. */
      by: Path[];
      /** The order to sort, ASC or DESC. */
      order: SortOrder;
    } | null;

    /** Row height when in list view (spreadsheet-like table). */
    rowHeightListPx: number;
  };
}

interface AppState {
  datasetState: {[datasetId: string]: DatasetState};
  // Whether the tasks panel in the top right is open.
  tasksPanelOpen: boolean;
  // Whether the search box is open.
  searchBoxOpen: boolean;
  searchBoxPages: SearchBoxPage[];
}

function getDatasetState(state: AppState, namespace: string, datasetName: string): DatasetState {
  const datasetId = `${namespace}/${datasetName}`;
  if (state.datasetState[datasetId] == null) {
    const initialState = {browser: {rowHeightListPx: 60}};
    if (Object.isExtensible(state.datasetState)) {
      state.datasetState[datasetId] = initialState;
    }
    return initialState;
  }
  return state.datasetState[datasetId];
}

export function useDataset(): DatasetState {
  const {namespace, datasetName} = useParams<{namespace: string; datasetName: string}>();
  if (namespace == null || datasetName == null) {
    throw new Error('Invalid route');
  }
  return useAppSelector((state) => getDatasetState(state.app, namespace, datasetName));
}

// Define the initial state using that type
const initialState: AppState = {
  tasksPanelOpen: false,
  searchBoxOpen: false,
  searchBoxPages: [],
  datasetState: {},
};

export const appSlice = createSlice({
  name: 'app',
  initialState,
  reducers: {
    setSelectedMediaPaths(
      state,
      action: PayloadAction<{namespace: string; datasetName: string; paths: Path[]}>
    ) {
      const {namespace, datasetName, paths} = action.payload;
      getDatasetState(state, namespace, datasetName).browser.selectedMediaPaths = paths;
    },
    setSelectedMetadataPaths(
      state,
      action: PayloadAction<{namespace: string; datasetName: string; paths: Path[]}>
    ) {
      const {namespace, datasetName, paths} = action.payload;
      getDatasetState(state, namespace, datasetName).browser.selectedMetadataPaths = paths;
    },
    setSort(
      state,
      action: PayloadAction<{
        namespace: string;
        datasetName: string;
        sort: {
          by: Path[];
          order: SortOrder;
        } | null;
      }>
    ) {
      const {namespace, datasetName, sort} = action.payload;
      getDatasetState(state, namespace, datasetName).browser.sort = sort;
    },
    setRowHeightListPx(
      state,
      action: PayloadAction<{namespace: string; datasetName: string; height: number}>
    ) {
      const {namespace, datasetName, height} = action.payload;
      getDatasetState(state, namespace, datasetName).browser.rowHeightListPx = height;
    },
    setTasksPanelOpen(state, action: PayloadAction<boolean>) {
      state.tasksPanelOpen = action.payload;
    },
    setSearchBoxOpen(state, action: PayloadAction<boolean>) {
      state.searchBoxOpen = action.payload;
    },
    pushSearchBoxPage(state, action: PayloadAction<SearchBoxPage>) {
      state.searchBoxPages.push(action.payload);
    },
    popSearchBoxPage(state) {
      state.searchBoxPages.pop();
    },
    setSearchBoxPages(state, action: PayloadAction<SearchBoxPage[]>) {
      state.searchBoxPages = action.payload;
    },
    setActiveConcept(
      state,
      action: PayloadAction<{
        namespace: string;
        datasetName: string;
        activeConcept: {
          concept: ConceptInfo;
          column: Path;
          embedding: EmbeddingInfo;
        } | null;
      }>
    ) {
      const {namespace, datasetName, activeConcept} = action.payload;
      getDatasetState(state, namespace, datasetName).activeConcept = activeConcept;
    },
  },
});
export const serverApi = createApi({
  reducerPath: 'serverApi',
  baseQuery: fastAPIBaseQuery(),
  endpoints: (builder) => ({
    getTaskManifest: builder.query<TaskManifest, void>({
      query: () => () => TasksService.getTaskManifest(),
    }),
  }),
});

/** Log a warning and show a toast notification when we get errors from the server. */
const rtkQueryErrorLogger: Middleware = () => (next) => (action) => {
  if (isRejectedWithValue(action)) {
    const errorToast = renderError(action.payload);
    // Imperatively render the component.
    const container = document.createElement('div');
    createRoot(container).render(errorToast);
    document.body.appendChild(container);
  }

  return next(action);
};

// Create the root reducer separately so we can extract the RootState type
const rootReducer = combineReducers({
  [appSlice.name]: appSlice.reducer,
  [serverApi.reducerPath]: serverApi.reducer,
  [datasetApi.reducerPath]: datasetApi.reducer,
  [conceptApi.reducerPath]: conceptApi.reducer,
  [signalApi.reducerPath]: signalApi.reducer,
  [embeddingApi.reducerPath]: embeddingApi.reducer,
});

export const setupStore = (preloadedState?: PreloadedState<RootState>) => {
  return configureStore({
    reducer: rootReducer,
    middleware: (getDefaultMiddleware) =>
      getDefaultMiddleware().concat([
        datasetApi.middleware,
        conceptApi.middleware,
        signalApi.middleware,
        serverApi.middleware,
        embeddingApi.middleware,
        rtkQueryErrorLogger,
      ]),
    preloadedState,
  });
};
export const store = setupStore();

// Export the actions.
export const {
  setActiveConcept,
  setTasksPanelOpen,
  setSearchBoxOpen,
  setSearchBoxPages,
  pushSearchBoxPage,
  popSearchBoxPage,
  setSelectedMediaPaths,
  setSelectedMetadataPaths,
  setSort,
  setRowHeightListPx,
} = appSlice.actions;

export const {useGetTaskManifestQuery, useLazyGetTaskManifestQuery} = serverApi;

/** Fetches the data associated with an item from the dataset. */
export function useGetItem(
  namespace: string,
  datasetName: string,
  itemId: string
): {isFetching: boolean; item: Item | null; error?: unknown} {
  const filters: Filter[] = [{path: [UUID_COLUMN], comparison: 'equals', value: itemId}];
  const {
    isFetching,
    currentData: items,
    error,
  } = useSelectRowsQuery({namespace, datasetName, options: {filters, limit: 1}});
  const item = items != null ? items[0] : null;
  return {isFetching, item, error};
}

/** Fetches a set of ids from the dataset that satisfy the specified filters. */
export function useGetIds(
  namespace: string,
  datasetName: string,
  filters: Filter[],
  activeConcept: ActiveConceptState | null | undefined,
  limit: number,
  offset: number,
  sortBy?: Path[],
  sortOrder?: SortOrder
): {isFetching: boolean; ids: string[] | null; error?: unknown} {
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
    const transform: SignalTransform = {signal};
    const conceptColumn: Column = {feature: activeConcept.column, transform, alias};
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

// See: https://react-redux.js.org/tutorials/typescript-quick-start
export type RootState = ReturnType<typeof rootReducer>;
export type AppStore = ReturnType<typeof setupStore>;
export type AppDispatch = typeof store.dispatch;
