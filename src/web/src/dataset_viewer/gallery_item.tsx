import * as React from 'react';
import {getLeafVals, Item, LeafValue, Path, serializePath} from '../schema';
import {useGetItem} from '../store/store';
import {renderError, renderPath, roundNumber} from '../utils';
import './dataset_viewer.module.css';
import styles from './gallery_item.module.css';

export interface GalleryItemProps {
  namespace: string;
  datasetName: string;
  itemId: string;
  mediaPaths: Path[];
  metadataPaths?: Path[];
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
function renderCell(item: Item, path: Path): JSX.Element {
  const leafVals = getLeafVals(item);
  const vals = leafVals[serializePath(path)];
  if (vals == null) {
    // The path doesn't exist in this item.
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

function GalleryMedia({item, path}: {item: Item | null; path: Path}): JSX.Element {
  const label = renderPath(path);
  const mediaContent = item != null ? renderCell(item, path) : 'Loading...';
  return (
    <div className={styles.media_container}>
      <div className={`${styles.media_label} truncate`}>{label}</div>
      <div className={styles.media_content_container}>
        <div className={styles.media_content}>{mediaContent}</div>
      </div>
    </div>
  );
}

function GalleryMetadata({item, paths}: {item: Item | null; paths?: Path[]}): JSX.Element {
  if (paths == null) {
    return <></>;
  }
  const metadata = paths.map((path) => {
    const pathKey = serializePath(path);
    return (
      <div key={pathKey} className="flex justify-between w-full text-sm">
        <div className={`${styles.metadata_field} ${styles.metadata_key}`}>{renderPath(path)}</div>
        <div className={styles.metadata_field}>
          {item != null ? renderCell(item, path) : 'Loading...'}
        </div>
      </div>
    );
  });
  return (
    <div className="mt-4">
      <div className={styles.metadata_label}>Metadata</div>
      {metadata}
    </div>
  );
}

export const GalleryItem = React.memo(function GalleryItem({
  namespace,
  datasetName,
  itemId,
  mediaPaths,
  metadataPaths,
}: GalleryItemProps): JSX.Element {
  const {item, error} = useGetItem(namespace, datasetName, itemId);
  if (error) {
    return <div>{renderError(error)}</div>;
  }
  const medias = mediaPaths.map((path) => {
    return <GalleryMedia key={serializePath(path)} item={item} path={path} />;
  });

  return (
    <>
      <div className={styles.overview}>
        {medias}
        <GalleryMetadata item={item} paths={metadataPaths} />
      </div>
    </>
  );
});
