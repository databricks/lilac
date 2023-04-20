import {SlTooltip} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';

import {getLeafVals, Item, LeafValue, Path, serializePath} from '../schema';
import {useGetItem} from '../store/store';
import {renderError, renderPath, roundNumber} from '../utils';
import './dataset_viewer.module.css';

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
function renderCell(item: Item, path: Path): string {
  const leafVals = getLeafVals(item);
  const vals = leafVals[serializePath(path)];
  if (vals == null) {
    // The path doesn't exist in this item.
    return 'N/A';
  }
  if (vals.length === 1) {
    return renderValue(vals[0]);
  }
  return vals.map((v) => renderValue(v)).join(', ');
}

function Media({item, path}: {item: Item | null; path: Path}): JSX.Element {
  const label = renderPath(path);
  const mediaContent = item != null ? renderCell(item, path) : 'Loading...';
  return (
    <div>
      <div className="truncate text-sm text-gray-500">{label}</div>
      <div className="rounded-lg bg-gray-100 p-2 text-gray-900">
        <div className="line-clamp-5 leading-6">{mediaContent}</div>
      </div>
    </div>
  );
}

function Metadata({item, paths}: {item: Item | null; paths?: Path[]}): JSX.Element {
  if (paths == null || paths.length == 0) {
    return <></>;
  }
  const metadata = paths.map((path) => {
    const pathKey = serializePath(path);
    const pathStr = renderPath(path);
    const content = item != null ? renderCell(item, path) : 'Loading...';
    return (
      <div key={pathKey} className=" flex w-full justify-between gap-2 text-sm">
        <SlTooltip content={pathStr} hoist>
          <div className="min-w-[1rem] truncate font-mono">{pathStr}</div>
        </SlTooltip>
        <SlTooltip content={content} hoist>
          <div className="min-w-[1rem] truncate">{content}</div>
        </SlTooltip>
      </div>
    );
  });
  return (
    <div className="mt-4">
      <div className="text-sm text-gray-500">Metadata</div>
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
    return <Media key={serializePath(path)} item={item} path={path} />;
  });

  return (
    <div className="mb-4 border p-2">
      {medias}
      <Metadata item={item} paths={metadataPaths} />
    </div>
  );
});
