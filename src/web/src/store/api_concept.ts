/**
 * RTK Query APIs for the concepts service: 'concepts' tag in FastAPI.
 */
import {createApi} from '@reduxjs/toolkit/dist/query/react';
import {ConceptsService, SignalInfo} from '../../fastapi_client';
import {fastAPIBaseQuery} from './api_utils';

const CONCEPTS_TAG = 'concepts';
export const signalApi = createApi({
  reducerPath: 'conceptApi',
  baseQuery: fastAPIBaseQuery(),
  tagTypes: [CONCEPTS_TAG],
  endpoints: (builder) => ({
    getConcepts: builder.query<SignalInfo[], void>({
      query: () => () => ConceptsService.getConcept(),
    }),
  }),
});

export const {useGetSignalsQuery} = signalApi;
