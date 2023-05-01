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
import {useGetManifestQuery} from '../store/apiDataset';
import styles from './DatasetViewer.module.css';
import {EmbedingsView} from './EmbedingsView';
import {GalleryView} from './GalleryView';
import {Stats} from './Stats';

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
  const gallery = <GalleryView namespace={namespace} datasetName={datasetName}></GalleryView>;

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
