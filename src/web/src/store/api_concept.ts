/**
 * RTK Query APIs for the concepts service: 'concepts' tag in FastAPI.
 */
import {createApi} from '@reduxjs/toolkit/dist/query/react';
import {ConceptInfo, ConceptsService} from '../../fastapi_client';
import {fastAPIBaseQuery} from './api_utils';

const CONCEPTS_TAG = 'concepts';
export const conceptApi = createApi({
  reducerPath: 'conceptApi',
  baseQuery: fastAPIBaseQuery(),
  tagTypes: [CONCEPTS_TAG],
  endpoints: (builder) => ({
    getConcepts: builder.query<ConceptInfo[], void>({
      query: () => () => ConceptsService.getConcepts(),
    }),
  }),
});

export const {useGetConceptsQuery} = conceptApi;
