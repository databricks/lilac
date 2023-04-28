import {
  SlIcon,
  SlSpinner,
  SlSplitPanel,
  SlTab,
  SlTabGroup,
  SlTabPanel,
} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {useParams} from 'react-router-dom';
import {useGetManifestQuery} from '../store/api_dataset';
import styles from './dataset_viewer.module.css';
import {EmbedingsView} from './embeddings_view';
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
  const statsView = <Stats namespace={namespace} datasetName={datasetName}></Stats>;
  const embeddingsView = (
    <EmbedingsView namespace={namespace} datasetName={datasetName}></EmbedingsView>
  );
  const gallery = <Gallery namespace={namespace} datasetName={datasetName}></Gallery>;

  return (
    <div className={`${styles.body} flex h-full w-full overflow-hidden`}>
      <SlSplitPanel position={65} className="h-full w-full">
        <SlIcon slot="handle" name="grip-vertical" />
        <div slot="start" className={`h-full w-full overflow-scroll`}>
          {gallery}
        </div>
        <div slot="end" className={`h-full w-full overflow-scroll`}>
          <SlTabGroup>
            <SlTab slot="nav" panel="stats">
              Stats
            </SlTab>
            <SlTab slot="nav" panel="embeddings">
              Embeddings
            </SlTab>
            <SlTabPanel name="stats">
              <div className="px-4">{statsView}</div>
            </SlTabPanel>
            <SlTabPanel name="embeddings">
              <div className="px-4">{embeddingsView}</div>
            </SlTabPanel>
          </SlTabGroup>
        </div>
      </SlSplitPanel>
    </div>
  );
});
