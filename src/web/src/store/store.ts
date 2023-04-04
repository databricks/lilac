/**
 * The global application redux state store.
 */
import {configureStore} from '@reduxjs/toolkit';
import {createApi} from '@reduxjs/toolkit/query/react';

import {createSlice} from '@reduxjs/toolkit';
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
import {datasetApi} from './api_dataset';
import {dataLoaderApi} from './api_data_loader';

// eslint-disable-next-line @typescript-eslint/no-empty-interface
interface AppState {}

// Define the initial state using that type
const initialState: AppState = {};

const appSlice = createSlice({
  name: 'app',
  initialState,
  reducers: {},
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
    [dataLoaderApi.reducerPath]: dataLoaderApi.reducer,
    [datasetApi.reducerPath]: datasetApi.reducer,
  },
  middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat([dbApi.middleware]),
  devTools: process.env.NODE_ENV !== 'production',
});

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

// See: https://react-redux.js.org/tutorials/typescript-quick-start
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
