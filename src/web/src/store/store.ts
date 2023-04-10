/**
 * The global application redux state store.
 */
import {configureStore, PayloadAction, SerializedError} from '@reduxjs/toolkit';
import {createApi} from '@reduxjs/toolkit/query/react';

import {createSlice} from '@reduxjs/toolkit';
import {Filter} from '../../fastapi_client';
import {Item, Path, UUID_COLUMN} from '../schema';
import {
  AddDatasetOptions,
  AddExamplesOptions,
  CreateModelOptions,
  CreateModelResponse,
  ListModelsResponse,
  LoadModelResponse,
  ModelInfo,
  ModelOptions,
  SaveModelOptions,
  SearchExamplesOptions,
  SearchExamplesResponse,
} from '../server_api_deprecated';
import {datasetApi, useSelectRowsQuery} from './api_dataset';

interface SelectedData {
  namespace?: string;
  datasetName?: string;

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
  selectedData: SelectedData;
}

// Define the initial state using that type
const initialState: AppState = {
  selectedData: {browser: {rowHeightListPx: 60}},
};

const appSlice = createSlice({
  name: 'app',
  initialState,
  reducers: {
    setDataset(state, action: PayloadAction<{namespace: string; datasetName: string}>) {
      state.selectedData.namespace = action.payload.namespace;
      state.selectedData.datasetName = action.payload.datasetName;
      state.selectedData.browser.selectedMediaPaths = undefined;
    },
    setSelectedMediaPaths(state, action: PayloadAction<Path[]>) {
      state.selectedData.browser.selectedMediaPaths = action.payload;
    },
    setSelectedMetadataPaths(state, action: PayloadAction<Path[]>) {
      state.selectedData.browser.selectedMetadataPaths = action.payload;
    },
    setRowHeightListPx(state, action: PayloadAction<number>) {
      state.selectedData.browser.rowHeightListPx = action.payload;
    },
  },
});

const MODELS_TAG = 'models';
const MODEL_DATA_TAG = 'model_data';
export const dbApi = createApi({
  reducerPath: 'dpiApi',
  baseQuery: () => {
    return {error: 'baseQuery should never be called.'};
  },
  tagTypes: [MODELS_TAG, MODEL_DATA_TAG],
  endpoints: (builder) => ({
    modelInfo: builder.query<ModelInfo, ModelOptions>({
      queryFn: async (options) => {
        const {username, name} = options;
        if (username == null || name == null) {
          return {data: null};
        }
        const response = await fetch(`/db/model_info?username=${username}&name=${name}`);
        return {data: await response.json()};
      },
    }),
    loadModel: builder.query<LoadModelResponse, ModelOptions>({
      queryFn: async (options) => {
        const {username, name} = options;
        if (username == null || name == null) {
          return {data: null};
        }
        const response = await fetch(`/db/load_model?username=${username}&name=${name}`);
        return {data: await response.json()};
      },
      providesTags: [MODEL_DATA_TAG],
    }),
    searchExamples: builder.query<SearchExamplesResponse, SearchExamplesOptions>({
      queryFn: async (options) => {
        const {username, modelName, query} = options;
        if (username == null || modelName == null || query == '') {
          return {data: null};
        }
        const response = await fetch(
          `/db/search_examples?username=${username}&model_name=${modelName}&query=${query}`
        );
        return {data: await response.json()};
      },
    }),
    listModels: builder.query<
      // A row of the 'model' table.
      ListModelsResponse,
      void
    >({
      queryFn: async () => {
        const response = await fetch(`/db/list_models`);
        return {data: await response.json()};
      },
      providesTags: [MODELS_TAG],
    }),
    createModel: builder.mutation<CreateModelResponse, CreateModelOptions>({
      queryFn: async (options) => {
        const createModelResponse = await fetch(`/db/create_model`, {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(options),
        });
        if (createModelResponse.status != 200) {
          return {error: `/db/create_model returned status code ${createModelResponse.status}.`};
        }

        const createModelResponseJson: CreateModelResponse = await createModelResponse.json();
        return {data: createModelResponseJson};
      },
      // Invalidate the list of datasets to force a refetch.
      invalidatesTags: [MODELS_TAG],
    }),
    saveModel: builder.mutation<null, SaveModelOptions>({
      queryFn: async (options) => {
        const saveModelResponse = await fetch(`/db/save_model`, {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(options),
        });
        if (saveModelResponse.status != 200) {
          return {
            error: `/db/save_model returned status code ${saveModelResponse.status}.
            ${await saveModelResponse.text()}`,
          };
        }

        return {data: null};
      },
      // Invalidate the model data.
      // NOTE: This is very inneficient as it causes *all* data to be invalidated. We can update
      // this later as we figure out the data loading story.
      invalidatesTags: [MODEL_DATA_TAG],
    }),
    addExamples: builder.mutation<null, AddExamplesOptions>({
      queryFn: async (options) => {
        const addExamplesResponse = await fetch(`/db/add_examples`, {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(options),
        });
        if (addExamplesResponse.status != 200) {
          return {
            error: `/db/save_model returned status code ${addExamplesResponse.status}.
            ${await addExamplesResponse.text()}`,
          };
        }

        return {data: null};
      },
      // Invalidate the model data.
      // NOTE: This is very inneficient as it causes *all* data to be invalidated. We can update
      // this later as we figure out the data loading story.
      invalidatesTags: [MODEL_DATA_TAG],
    }),
    addModelData: builder.mutation<null, AddDatasetOptions>({
      queryFn: async (options) => {
        const addDatasetResponse = await fetch(`/db/add_dataset`, {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(options),
        });
        if (addDatasetResponse.status != 200) {
          return {error: `/db/add_dataset returned status code ${addDatasetResponse.status}.`};
        }

        return {data: null};
      },
      // Invalidate the model data.
      // NOTE: This is very inneficient as it causes *all* data to be invalidated. We can update
      // this later as we figure out the data loading story.
      invalidatesTags: [MODEL_DATA_TAG],
    }),
  }),
});

export const store = configureStore({
  reducer: {
    [appSlice.name]: appSlice.reducer,
    [dbApi.reducerPath]: dbApi.reducer,
    [datasetApi.reducerPath]: datasetApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat([dbApi.middleware, datasetApi.middleware]),
  devTools: process.env.NODE_ENV !== 'production',
});

// Export the actions.
export const {setDataset, setSelectedMediaPaths, setSelectedMetadataPaths, setRowHeightListPx} =
  appSlice.actions;

export const {
  useCreateModelMutation,
  useModelInfoQuery,
  useListModelsQuery,
  useLoadModelQuery,
  useAddModelDataMutation,
  useSaveModelMutation,
  useAddExamplesMutation,
  useLazySearchExamplesQuery,
} = dbApi;

/** Fetches the data associated with an item from the dataset. */
export function useGetItem(
  namespace: string,
  datasetName: string,
  itemId: string
): {isFetching: boolean; item: Item | null; error?: SerializedError | string} {
  const filters: Filter[] = [{path: [UUID_COLUMN], comparison: 'equals', value: itemId}];
  const {
    isFetching,
    currentData: items,
    error,
  } = useSelectRowsQuery({namespace, datasetName, options: {filters}});
  const item = items != null ? items[0] : null;
  return {isFetching, item, error};
}

/** Fetches a set of ids from the dataset that satisfy the specified filters. */
export function useGetIds(
  namespace: string,
  datasetName: string,
  limit: number,
  offset: number
): {isFetching: boolean; ids: string[] | null; error?: SerializedError | string} {
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

// See: https://react-redux.js.org/tutorials/typescript-quick-start
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
