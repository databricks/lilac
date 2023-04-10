import {SlOption, SlSelect} from '@shoelace-style/shoelace/dist/react';
import {useVirtualizer} from '@tanstack/react-virtual';
import * as React from 'react';
import {DataType, Field, StatsResult, WebManifest} from '../../fastapi_client';
import {useAppDispatch, useAppSelector} from '../hooks';
import {Path, Schema, serializePath} from '../schema';
import {useGetManifestQuery, useGetMultipleStatsQuery} from '../store/api_dataset';
import {setBrowserPreviewPaths, useGetIds} from '../store/store';
import {renderPath} from '../utils';
import {GalleryItem} from './gallery_item';
import styles from './gallery_view.module.css';

export interface GalleryProps {
  namespace: string;
  datasetName: string;
}

/** Number of items to be fetched when fetching the next page. */
const ITEMS_PAGE_SIZE = 40;

/**
 * A hook that allows for infinite fetch with paging. The hook exports fetchNextPage which should
 * be called by users to fetch the next page.
 */
function useInfiniteItemsQuery(namespace: string, datasetName: string) {
  const datasetId = `${namespace}/${datasetName}`;
  const [prevIds, setPrevIds] = React.useState<{[datasetId: string]: string[]}>({});
  const cachedIds = prevIds[datasetId] || [];
  const {error, isFetching, ids} = useGetIds(
    namespace,
    datasetName,
    ITEMS_PAGE_SIZE,
    cachedIds.length
  );
  const allIds = cachedIds.concat(ids || []);
  const hasNextPage = ids == null || ids.length === ITEMS_PAGE_SIZE;

  function fetchNextPage() {
    // Remember the previous ids. Key by `datasetId` so that we invalidate when the dataset changes.
    setPrevIds({[datasetId]: allIds});
  }

  return {
    allIds,
    error,
    isFetchingNextPage: isFetching,
    hasNextPage,
    fetchNextPage,
  };
}

export interface GalleryMenuProps {
  schema: Schema;
  previewPaths: Path[];
}

interface VisualLeaf {
  dtype: DataType | 'image';
}

// TODO(smilkov): Remove this once we make a logical image dtype.
export const IMAGE_PATH_PREFIX = '__image__';

export const GalleryMenu = React.memo(function GalleryMenu({
  schema,
  previewPaths,
}: GalleryMenuProps): JSX.Element {
  const dispatch = useAppDispatch();
  const leafs: [Path, VisualLeaf | Field][] = [...schema.leafs];

  const items = leafs.map(([path, field], i) => {
    return (
      <SlOption key={i} value={i.toString()}>
        {renderPath(path)} : {field.dtype}
      </SlOption>
    );
  });

  const previewPathsSet = new Set(previewPaths.map((p) => serializePath(p)));
  const selectedIndices: string[] = [];
  let index = 0;
  for (const [path] of leafs) {
    if (previewPathsSet.has(serializePath(path))) {
      selectedIndices.push(index.toString());
    }
    index++;
  }

  const previewPathsChanged = (indices: string[]) => {
    if (indices === selectedIndices) {
      // Avoids an infinite loop (bug in Shoelace select component) where setting the value
      // declaratively below leads to firing onChange.
      return;
    }
    const paths = indices.map((index) => leafs[Number(index)][0]);
    dispatch(setBrowserPreviewPaths(paths));
  };

  return (
    <div className="flex h-16">
      {/* Features preview dropdown. */}
      <div className="flex flex-col w-96">
        <div>
          <label>Preview features</label>
        </div>
        <div className="flex h-full items-center">
          <SlSelect
            className={`mr-2 w-full ${styles.gallery_preview_dropdown}`}
            size="small"
            value={selectedIndices}
            placeholder="Select fields to preview"
            multiple
            maxOptionsVisible={2}
            hoist={true}
            onSlChange={(e) =>
              previewPathsChanged((e.target as HTMLInputElement).value as unknown as string[])
            }
          >
            {items}
          </SlSelect>
        </div>
      </div>
    </div>
  );
});

export interface GalleryRowProps {
  /** List of run ids to render in a single row. */
  namespace: string;
  datasetName: string;
  itemIds: string[];
  previewPaths: Path[];
}

export const GalleryRow = React.memo(function GalleryRow({
  namespace,
  datasetName,
  itemIds,
  previewPaths,
}: GalleryRowProps): JSX.Element {
  const galleryItems = itemIds.map((itemId) => {
    return (
      <GalleryItem
        key={itemId}
        namespace={namespace}
        datasetName={datasetName}
        itemId={itemId}
        previewPaths={previewPaths!}
      ></GalleryItem>
    );
  });
  return <div className="flex w-full h-full py-px">{galleryItems}</div>;
});

export function usePreviewPaths(
  namespace: string,
  datasetName: string,
  manifest: WebManifest | null | undefined,
  schema: Schema | null
): Path[] {
  const stringLeafs: Path[] = [];
  if (manifest != null && schema != null) {
    for (const [path, field] of schema.leafs) {
      if (field.dtype === 'string') {
        stringLeafs.push(path);
      }
    }
  }
  let previewPaths = useAppSelector((state) => state.app.selectedData.browser.previewPaths);
  const multipleStats = useGetMultipleStatsQuery({namespace, datasetName, leafPaths: stringLeafs});
  previewPaths = React.useMemo(() => {
    if (previewPaths != null) {
      return previewPaths;
    }
    if (manifest == null) {
      return [];
    }

    // If no media leaf is found, select the longest string.
    if (multipleStats.currentData == null) {
      return [];
    }
    const stringLeafsByLength = multipleStats.currentData
      .map((x, i) => [i, x] as [number, StatsResult])
      .sort(([, a], [, b]) => {
        // `avg_text_length` is always defined for string leafs.
        return b.avg_text_length! - a.avg_text_length!;
      });
    const longestLeafIndex = stringLeafsByLength[0][0];
    return [stringLeafs[longestLeafIndex]];
  }, [manifest, previewPaths, multipleStats.currentData]);
  return previewPaths;
}

export const Gallery = React.memo(function Gallery({
  namespace,
  datasetName,
}: GalleryProps): JSX.Element {
  const {
    currentData: webManifest,
    isFetching: isManifestFetching,
    error: manifestError,
  } = useGetManifestQuery({namespace, datasetName});
  const schema = webManifest != null ? new Schema(webManifest.dataset_manifest.data_schema) : null;
  const previewPaths = usePreviewPaths(namespace, datasetName, webManifest, schema);

  const {error, isFetchingNextPage, allIds, hasNextPage, fetchNextPage} = useInfiniteItemsQuery(
    namespace,
    datasetName
  );
  // `useVirtualizer needs a reference to the scrolling element below.
  const parentRef = React.useRef<HTMLDivElement | null>(null);
  const [itemsPerRow, setItemsPerRow] = React.useState(1);
  const itemWidthPx = 500;
  const numRows = Math.ceil(allIds.length / itemsPerRow);

  const virtualizer = useVirtualizer({
    count: hasNextPage ? numRows + 1 : numRows,
    getScrollElement: () => parentRef.current || null,
    // The estimated height of an individual item in pixels. This doesn't matter since we will
    // compute the actual height after the initial render.
    estimateSize: () => 200,
    overscan: 1,
  });

  React.useEffect(
    function maybeFetchNextPage() {
      const lastVirtualRow = virtualizer.getVirtualItems().slice().reverse()[0];
      if (lastVirtualRow == null) {
        return;
      }
      if (lastVirtualRow.index >= numRows && hasNextPage && !isFetchingNextPage) {
        fetchNextPage();
      }
    },
    [hasNextPage, fetchNextPage, numRows, isFetchingNextPage, virtualizer.getVirtualItems()]
  );

  React.useEffect(
    function addResizeObserver() {
      if (parentRef.current == null) {
        return;
      }
      const observer = new ResizeObserver((entries) => {
        const galleryWidthPx = entries[0].contentRect.width;
        const itemsPerRow = Math.max(1, Math.round(galleryWidthPx / itemWidthPx));
        setItemsPerRow(itemsPerRow);
      });
      observer.observe(parentRef.current);
      return () => observer.disconnect();
    },
    [parentRef.current, webManifest]
  );

  if (error || manifestError) {
    return <div>Error: {((error || manifestError) as Error).message}</div>;
  }
  if (isManifestFetching) {
    return <div>Loading...</div>;
  }
  if (webManifest == null || schema == null) {
    return <>This should not happen since the manifest has loaded and there is no error</>;
  }
  const virtualRows = virtualizer.getVirtualItems();
  const transformY = virtualRows[0]?.start || 0;
  return (
    <div className="flex h-full w-full flex-col">
      <div className="mb-4">
        <GalleryMenu schema={schema} previewPaths={previewPaths}></GalleryMenu>
      </div>
      <div ref={parentRef} className="overflow-y-scroll h-full w-full">
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative',
          }}
        >
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              transform: `translateY(${transformY}px)`,
            }}
          >
            {virtualRows.map((virtualRow) => {
              const isLoaderRow = virtualRow.index >= numRows;
              const startIndex = virtualRow.index * itemsPerRow;
              const endIndex = (virtualRow.index + 1) * itemsPerRow;
              const itemIds = allIds.slice(startIndex, endIndex);

              return (
                <div
                  key={virtualRow.index}
                  data-index={virtualRow.index}
                  ref={virtualizer.measureElement}
                  style={{width: '100%'}}
                >
                  {isLoaderRow ? (
                    <div className={styles.loader_row}>Loading more...</div>
                  ) : (
                    <GalleryRow
                      namespace={namespace}
                      datasetName={datasetName}
                      itemIds={itemIds}
                      previewPaths={previewPaths!}
                    ></GalleryRow>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
});
