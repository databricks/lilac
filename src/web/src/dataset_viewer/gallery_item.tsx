import {SlButton} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {getLeafVals, Item, LeafValue, Path, serializePath} from '../schema';
import {useGetItem} from '../store/store';
import {renderError, roundNumber} from '../utils';
import './dataset_viewer.module.css';
import styles from './gallery_item.module.css';

export interface GalleryItemProps {
  namespace: string;
  datasetName: string;
  itemId: string;
  previewPaths: Path[];
}

/** Renders an individual value. Rounds floating numbers to 3 decimals. */
function renderValue(val: LeafValue): string {
  if (val == null) {
    return 'N/A';
  }
  if (typeof val === 'number') {
    return roundNumber(val, 3).toString();
  }
  return val.toString();
}

/** Renders an individual item, which can be an arbitrary nested struct with lists. */
function renderCell(item: Item, previewPath: Path): JSX.Element {
  const leafVals = getLeafVals(item);
  const vals = leafVals[serializePath(previewPath)];
  if (vals == null) {
    // The preview path doesn't exist in this item.
    return <>N/A</>;
  }
  if (vals.length === 1) {
    return <>{renderValue(vals[0])}</>;
  }
  return (
    <ul>
      {vals.map((v, i) => (
        <li key={i}>{renderValue(v)}</li>
      ))}
    </ul>
  );
}

export const GalleryItem = React.memo(function GalleryItem({
  namespace,
  datasetName,
  itemId,
  previewPaths,
}: GalleryItemProps): JSX.Element {
  const {isFetching, item, error} = useGetItem(namespace, datasetName, itemId);
  if (error) {
    return <div>{renderError(error)}</div>;
  }
  const isReady = !isFetching && item != null;
  const mediaContent = !isReady ? 'Loading...' : renderCell(item, previewPaths[0]);
  return (
    <>
      <div className={styles['card-overview']}>
        <div className={`card-media ${styles['card-media']}`}>{mediaContent}</div>
        <div slot="footer">
          <SlButton variant="primary" pill>
            Open
          </SlButton>
        </div>
      </div>
    </>
  );
});
