/**
 * RTK Query APIs for the dataset service: 'dataset' tag in FastAPI.
 */
import {createApi} from '@reduxjs/toolkit/dist/query/react';
import {DatasetInfo, DatasetService} from '../../fastapi_client';

export const datasetApi = createApi({
  reducerPath: 'datasetApi',
  baseQuery: () => {
    return {error: 'baseQuery should never be called.'};
  },
  endpoints: (builder) => ({
    getDatasets: builder.query<DatasetInfo[], void>({
      queryFn: async () => {
        return {data: await DatasetService.getDatasets()};
      },
    }),
  }),
});

export const {useGetDatasetsQuery} = datasetApi;
