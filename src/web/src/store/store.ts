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
  ConceptInfo,
  EmbeddingInfo,
  SortOrder,
  TaskManifest,
  TasksService,
} from '../../fastapi_client';
import {Path} from '../schema';

import {useParams} from 'react-router-dom';
import {useAppSelector} from '../hooks';
import {SearchBoxPage} from '../searchBox/SearchBox';
import {renderError} from '../utils';
import {conceptApi} from './apiConcept';
import {datasetApi} from './apiDataset';
import {embeddingApi} from './apiEmbeddings';
import {signalApi} from './apiSignal';
import {fastAPIBaseQuery} from './apiUtils';

export interface ActiveConceptState {
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

// See: https://react-redux.js.org/tutorials/typescript-quick-start
export type RootState = ReturnType<typeof rootReducer>;
export type AppStore = ReturnType<typeof setupStore>;
export type AppDispatch = typeof store.dispatch;
