import * as React from 'react';
//import styles from './dataset_loader.module.css';
import {useLoaderSourceFieldsQuery, useLoaderSourcesQuery} from './store/api_server_loader';

export const DatasetLoader = (): JSX.Element => {
  const sources = useLoaderSourcesQuery();
  const csvSource = useLoaderSourceFieldsQuery({sourceName: 'csv'});
  return sources.currentData != null ? (
    <>
      {sources.currentData.sources}
      {JSON.stringify(csvSource.currentData)}
    </>
  ) : (
    <>nuthin</>
  );
};
