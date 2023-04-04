import {SlSpinner} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {useParams} from 'react-router-dom';
import {useGetManifestQuery} from '../store/api_dataset';

export const DatasetViewer = React.memo(function DatasetViewer(): JSX.Element {
  const {namespace, datasetName} = useParams<{namespace: string; datasetName: string}>();
  if (namespace == null || datasetName == null) {
    throw new Error('Invalid route');
  }
  const {isFetching, currentData} = useGetManifestQuery({namespace, datasetName});
  if (isFetching || currentData == null) {
    return <SlSpinner />;
  }
  return (
    <>
      Viewing dataset {namespace} / {datasetName}
    </>
  );
});
