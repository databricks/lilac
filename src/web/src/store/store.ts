/**
 * The global application redux state store.
 */
import type {Middleware} from '@reduxjs/toolkit';
import {configureStore, createSlice, isRejectedWithValue, PayloadAction} from '@reduxjs/toolkit';
import {createApi} from '@reduxjs/toolkit/query/react';
import {createRoot} from 'react-dom/client';
import {
  ConceptInfo,
  EmbeddingInfo,
  Field,
  Filter,
  NamedBins,
  StatsResult,
  TaskManifest,
  TasksService,
} from '../../fastapi_client';
import {getEqualBins, getNamedBins, NUM_AUTO_BINS, TOO_MANY_DISTINCT} from '../db';
import {isOrdinal, isTemporal, Item, LeafValue, Path, UUID_COLUMN} from '../schema';

import {renderError} from '../utils';
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

interface ActiveDatasetState {
  namespace?: string;
  datasetName?: string;

  // The active global concept. This is set when a column is actively being edited.
  activeConcept?: {
    concept: ConceptInfo;
    column: Path;
    embedding: EmbeddingInfo;
  } | null;

  browser: {
    /** A list of paths to preview as "media" in the gallery item. */
    selectedMediaPaths?: Path[];
    /** A list of paths to preview as metadata (non-media) in the gallery item .*/
    selectedMetadataPaths?: Path[];
    /** Row height when in list view (spreadsheet-like table). */
    rowHeightListPx: number;
  };
}

interface AppState {
  // The currently selected dataset.
  activeDataset: ActiveDatasetState;
  // Whether the tasks panel in the top right is open.
  tasksPanelOpen: boolean;
}

// Define the initial state using that type
const initialState: AppState = {
  activeDataset: {browser: {rowHeightListPx: 60}},
  tasksPanelOpen: false,
};

const appSlice = createSlice({
  name: 'app',
  initialState,
  reducers: {
    setDataset(state, action: PayloadAction<{namespace: string; datasetName: string}>) {
      state.activeDataset.namespace = action.payload.namespace;
      state.activeDataset.datasetName = action.payload.datasetName;
      state.activeDataset.browser.selectedMediaPaths = undefined;
    },
    setSelectedMediaPaths(state, action: PayloadAction<Path[]>) {
      state.activeDataset.browser.selectedMediaPaths = action.payload;
    },
    setSelectedMetadataPaths(state, action: PayloadAction<Path[]>) {
      state.activeDataset.browser.selectedMetadataPaths = action.payload;
    },
    setRowHeightListPx(state, action: PayloadAction<number>) {
      state.activeDataset.browser.rowHeightListPx = action.payload;
    },
    setTasksPanelOpen(state, action: PayloadAction<boolean>) {
      state.tasksPanelOpen = action.payload;
    },
    setActiveConcept(
      state,
      action: PayloadAction<{concept: ConceptInfo; column: Path; embedding: EmbeddingInfo} | null>
    ) {
      state.activeDataset.activeConcept = action.payload;
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

export const store = configureStore({
  reducer: {
    [appSlice.name]: appSlice.reducer,
    [serverApi.reducerPath]: serverApi.reducer,
    [datasetApi.reducerPath]: datasetApi.reducer,
    [conceptApi.reducerPath]: conceptApi.reducer,
    [signalApi.reducerPath]: signalApi.reducer,
    [embeddingApi.reducerPath]: embeddingApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat([
      datasetApi.middleware,
      conceptApi.middleware,
      signalApi.middleware,
      serverApi.middleware,
      embeddingApi.middleware,
      rtkQueryErrorLogger,
    ]),
  devTools: process.env.NODE_ENV !== 'production',
});

// Export the actions.
export const {
  setDataset,
  setActiveConcept,
  setTasksPanelOpen,
  setSelectedMediaPaths,
  setSelectedMetadataPaths,
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
  limit: number,
  offset: number
): {isFetching: boolean; ids: string[] | null; error?: unknown} {
  const filters: Filter[] = [];
  /** Select only the UUID column. */
  const columns: string[] = [UUID_COLUMN];
  const {
    isFetching,
    currentData: items,
    error,
  } = useSelectRowsQuery({namespace, datasetName, options: {filters, columns, limit, offset}});
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
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
