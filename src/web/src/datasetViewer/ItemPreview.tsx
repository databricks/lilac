import * as React from 'react';
import {useGetItem} from '../hooks/useGetItem';
import {getLeafVals, Item, LeafValue, Path, serializePath} from '../schema';
import {useGetMediaURLQuery} from '../store/apiDataset';
import {renderError, roundNumber} from '../utils';
import {IMAGE_PATH_PREFIX} from './Browser';
import styles from './ItemPreview.module.css';

export interface ItemPreviewProps {
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

/** Renders an individual image, attached to an item. */
export const ImageThumbnail = React.memo(function ImageThumbnail({
  namespace,
  datasetName,
  itemId,
  mediaPath,
}: {
  namespace: string;
  datasetName: string;
  itemId: string;
  mediaPath: Path;
}): JSX.Element {
  const {
    isFetching,
    currentData: mediaUrl,
    error,
  } = useGetMediaURLQuery({
    namespace,
    datasetName,
    itemId,
    leafPath: mediaPath,
  });
  if (error) {
    return renderError(error);
  }
  if (isFetching || mediaUrl == null) {
    return <>Loading...</>;
  }
  return <img className={`${styles.center_cropped} h-full w-full`} src={mediaUrl}></img>;
});

export const ItemPreview = React.memo(function ItemPreview({
  namespace,
  datasetName,
  itemId,
  previewPaths,
}: ItemPreviewProps): JSX.Element {
  const {isFetching, item, error} = useGetItem({namespace, datasetName, itemId});
  if (error) {
    return <div>{renderError(error)}</div>;
  }
  if (isFetching || item == null) {
    return <div>Loading...</div>;
  }
  const inGalleryMode = previewPaths.length === 1;
  const columns = previewPaths.map((previewPath, i) => {
    const isImage = previewPath[0] === IMAGE_PATH_PREFIX;
    let className = `grow w-full h-full overflow-hidden`;
    if (i > 0) {
      className += ' border-l';
    }
    if (isImage && inGalleryMode) {
      // Add only 1 pixel of margin between packed images.
      className += ' px-px';
    } else if (!isImage && inGalleryMode) {
      // Add border and text centering when packing tabular features.
      className += ' p-2 border flex justify-center';
    } else {
      className += ' px-2';
    }
    return (
      <div key={serializePath(previewPath)} className={className}>
        {isImage ? (
          <ImageThumbnail
            namespace={namespace}
            datasetName={datasetName}
            itemId={itemId}
            mediaPath={previewPath.slice(1)}
          ></ImageThumbnail>
        ) : (
          <div className={`${styles.text_preview} h-full`}>{renderCell(item, previewPath)}</div>
        )}
      </div>
    );
  });
  if (!inGalleryMode) {
    return <div className="flex h-full w-full border-b py-1">{columns}</div>;
  } else {
    return <>{columns}</>;
  }
});
