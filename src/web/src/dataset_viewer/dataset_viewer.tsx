import {SlIcon, SlSpinner, SlSplitPanel} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {useParams} from 'react-router-dom';
import {useGetManifestQuery} from '../store/api_dataset';
import styles from './dataset_viewer.module.css';
import {Gallery} from './gallery_view';
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
  const stats = <Stats namespace={namespace} datasetName={datasetName}></Stats>;
  const gallery = <Gallery namespace={namespace} datasetName={datasetName}></Gallery>;

  return (
    <div className={`${styles.body} flex h-full w-full overflow-hidden`}>
      <SlSplitPanel position={65} className="h-full w-full">
        <SlIcon slot="handle" name="grip-vertical" />
        <div slot="start" className={`h-full w-full p-4 ${styles.stats}`}>
          {gallery}
        </div>
        <div slot="end" className={`h-full w-full p-4 ${styles.browser}`}>
          {stats}
        </div>
      </SlSplitPanel>
    </div>
  );
});
