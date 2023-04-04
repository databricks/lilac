import * as React from 'react';
import {useGetSourceFieldsQuery, useGetSourcesQuery} from './store/api_data_loader';

export const DatasetLoader = (): JSX.Element => {
  const sources = useGetSourcesQuery();
  const csvSource = useGetSourceFieldsQuery({sourceName: 'csv'});
  return sources.currentData != null ? (
    <>
      {sources.currentData.sources}
      {JSON.stringify(csvSource.currentData)}
    </>
  ) : (
    <>nuthin</>
  );
};
