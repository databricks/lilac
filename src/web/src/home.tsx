import {SlSpinner} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {useGetDatasetsQuery} from './store/api_dataset';
import {renderError} from './utils';

export const Home = React.memo(function Home(): JSX.Element {
  const datasets = useGetDatasetsQuery();

  return (
    <>
      <div className="flex flex-col">
        <div className="flex flex-col">
          {datasets.isFetching ? (
            <SlSpinner />
          ) : datasets.error || datasets.currentData == null ? (
            renderError(datasets.error)
          ) : (
            datasets.currentData.map((datasetInfo) => (
              <div>
                {datasetInfo.namespace}/{datasetInfo.dataset_name}
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
});
