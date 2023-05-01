/**
 * RTK Query APIs for the dataset service: 'dataset' tag in FastAPI.
 */
import {createApi} from '@reduxjs/toolkit/dist/query/react';
import {EmbeddingInfo, EmbeddingsService} from '../../fastapi_client';
import {fastAPIBaseQuery} from './apiUtils';

const EMBEDDINGS_TAG = 'embeddings';
export const embeddingApi = createApi({
  reducerPath: 'embeddingApi',
  baseQuery: fastAPIBaseQuery(),
  tagTypes: [EMBEDDINGS_TAG],
  endpoints: (builder) => ({
    getEmbeddings: builder.query<EmbeddingInfo[], void>({
      query: () => () => EmbeddingsService.getEmbeddings(),
    }),
  }),
});

export const {useGetEmbeddingsQuery} = embeddingApi;
