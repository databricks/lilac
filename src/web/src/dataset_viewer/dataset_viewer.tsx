import {SlIcon, SlSpinner, SlSplitPanel} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {useParams} from 'react-router-dom';
import {useGetManifestQuery} from '../store/api_dataset';
import {Browser} from './browser';
import styles from './dataset_viewer.module.css';
import {Stats} from './stats';

export const DatasetViewer = React.memo(function DatasetViewer(): JSX.Element {
  const {namespace, datasetName} = useParams<{namespace: string; datasetName: string}>();
  if (namespace == null || datasetName == null) {
    throw new Error('Invalid route');
  }
  const {isFetching, currentData} = useGetManifestQuery({namespace, datasetName});
  if (isFetching || currentData == null) {
    return <SlSpinner />;
  }
  const statsUI = <Stats namespace={namespace} datasetName={datasetName}></Stats>;
  const browserUI = <Browser namespace={namespace} datasetName={datasetName}></Browser>;

  return (
    <div className={`${styles.body} flex w-full h-full overflow-hidden`}>
      <SlSplitPanel position={65} className="w-full h-full">
        <SlIcon slot="handle" name="grip-vertical" />
        <div slot="start" className={`p-4 h-full w-full ${styles.stats}`}>
          {statsUI}
        </div>
        <div slot="end" className={`p-4 h-full w-full ${styles.browser}`}>
          {browserUI}
        </div>
      </SlSplitPanel>
    </div>
  );
});
