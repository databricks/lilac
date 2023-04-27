import {SlButton, SlDrawer, SlOption, SlRange, SlSelect} from '@shoelace-style/shoelace/dist/react';
import {useVirtualizer} from '@tanstack/react-virtual';
import * as React from 'react';
import {DataType, Field, Filter, StatsResult, WebManifest} from '../../fastapi_client';
import {useAppDispatch} from '../hooks';
import {Path, Schema, serializePath} from '../schema';
import {useGetManifestQuery, useGetMultipleStatsQuery} from '../store/api_dataset';
import {setRowHeightListPx, setSelectedMediaPaths, useDataset, useGetIds} from '../store/store';
import {renderPath} from '../utils';
import styles from './browser.module.css';
import {ItemPreview} from './item_preview';

export interface BrowserProps {
  namespace: string;
  datasetName: string;
}

/** Number of items to be fetched when fetching the next page. */
const ITEMS_PAGE_SIZE = 90;

/**
 * A hook that allows for infinite fetch with paging. The hook exports fetchNextPage which should
 * be called by users to fetch the next page.
 */
function useInfiniteItemsQuery(namespace: string, datasetName: string) {
  const datasetId = `${namespace}/${datasetName}`;
  const sort = useDataset().browser.sort;
  const [prevIds, setPrevIds] = React.useState<{[datasetId: string]: string[]}>({});
  const cachedIds = prevIds[datasetId] || [];
  const filters: Filter[] = [];
  const activeConcept = null;
  const {error, isFetching, ids} = useGetIds(
    namespace,
    datasetName,
    filters,
    activeConcept,
    ITEMS_PAGE_SIZE,
    cachedIds.length,
    sort?.by,
    sort?.order
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

export interface BrowserMenuProps {
  namespace: string;
  datasetName: string;
  schema: Schema;
  previewPaths: Path[];
  rowHeightListPx: number;
}

interface VisualLeaf {
  dtype: DataType | 'image';
}

// TODO(smilkov): Remove this once we make a logical image dtype.
export const IMAGE_PATH_PREFIX = '__image__';

export const BrowserMenu = React.memo(function BrowserMenu({
  namespace,
  datasetName,
  schema,
  previewPaths,
  rowHeightListPx,
}: BrowserMenuProps): JSX.Element {
  const dispatch = useAppDispatch();
  const [drawerIsOpen, setDrawerIsOpen] = React.useState(false);
  const leafs: [Path, VisualLeaf | Field][] = [...schema.leafs];

  // TODO(smilkov): Add support for images.
  // for (const imageInfo of manifest.images) {
  //   const path = [IMAGE_PATH_PREFIX, ...imageInfo.path];
  //   leafs.push([path, {dtype: 'image'}]);
  // }

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
    dispatch(setSelectedMediaPaths({namespace, datasetName, paths}));
  };

  const rowHeightListChanged = (newRowHeightPx: number) => {
    dispatch(setRowHeightListPx({namespace, datasetName, height: newRowHeightPx}));
  };

  return (
    <div className="flex h-16">
      {/* Features preview dropdown. */}
      <div className="flex w-96 flex-col">
        <div>
          <label>Preview features</label>
        </div>
        <div className="flex h-full items-center">
          <SlSelect
            className={`mr-2 w-full ${styles.browser_preview_dropdown}`}
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

      {/* Settings button */}
      <div className="flex flex-col">
        <div>
          <label>&nbsp;</label>
        </div>
        <div className="flex h-full items-center">
          <SlButton size="small" onClick={() => setDrawerIsOpen(true)}>
            Settings
          </SlButton>
        </div>
      </div>
      <SlDrawer
        label="Browser settings"
        placement="start"
        open={drawerIsOpen}
        onSlAfterHide={() => setDrawerIsOpen(false)}
      >
        <div className="font-bold">Row height (pixels)</div>
        <div className="flex items-center justify-between">
          <label>List view</label>
          <div>
            <SlRange
              min={40}
              max={500}
              value={rowHeightListPx}
              step={5}
              onSlChange={(e) =>
                rowHeightListChanged((e.target as HTMLInputElement).value as unknown as number)
              }
            />
          </div>
        </div>
      </SlDrawer>
    </div>
  );
});

export interface BrowserRowProps {
  /** List of run ids to render in a single row. */
  namespace: string;
  datasetName: string;
  itemIds: string[];
  previewPaths: Path[];
}

export const BrowserRow = React.memo(function BrowserRow({
  namespace,
  datasetName,
  itemIds,
  previewPaths,
}: BrowserRowProps): JSX.Element {
  const itemPreviews = itemIds.map((itemId) => {
    return (
      <ItemPreview
        key={itemId}
        namespace={namespace}
        datasetName={datasetName}
        itemId={itemId}
        previewPaths={previewPaths!}
      ></ItemPreview>
    );
  });
  return <div className="flex h-full w-full py-px">{itemPreviews}</div>;
});

export function usePreviewPaths(
  namespace: string,
  datasetName: string,
  manifest: WebManifest | null | undefined,
  schema: Schema | null
): Path[] {
  const stringLeafs = React.useMemo(() => {
    if (manifest != null && schema != null) {
      return schema.leafs.filter(([, field]) => field.dtype === 'string').map(([path]) => path);
    }
    return [];
  }, [manifest, schema]);

  let previewPaths = useDataset().browser.selectedMediaPaths;
  const multipleStats = useGetMultipleStatsQuery({namespace, datasetName, leafPaths: stringLeafs});
  previewPaths = React.useMemo(() => {
    if (previewPaths != null) {
      return previewPaths;
    }
    if (manifest == null) {
      return [];
    }

    // TODO(smilkov): Add support for images.
    // Auto-select the first media leaf.
    // if (manifest.images.length > 0) {
    //   const imageInfo = manifest.images[0];
    //   const imagePath: Path = [IMAGE_PATH_PREFIX, ...imageInfo.path];
    //   return [imagePath];
    // }

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
  }, [previewPaths, manifest, multipleStats.currentData, stringLeafs]);
  return previewPaths;
}

export const Browser = React.memo(function Browser({
  namespace,
  datasetName,
}: BrowserProps): JSX.Element {
  const {
    currentData: webManifest,
    isFetching: isManifestFetching,
    error: manifestError,
  } = useGetManifestQuery({namespace, datasetName});
  const schema = webManifest != null ? new Schema(webManifest.dataset_manifest.data_schema) : null;
  const previewPaths = usePreviewPaths(namespace, datasetName, webManifest, schema);
  const rowHeightListPx = useDataset().browser.rowHeightListPx;
  const inGalleryMode = previewPaths.length === 1;
  const rowHeightPx = rowHeightListPx;

  const {error, isFetchingNextPage, allIds, hasNextPage, fetchNextPage} = useInfiniteItemsQuery(
    namespace,
    datasetName
  );
  // `useVirtualizer needs a reference to the scrolling element below.
  const parentRef = React.useRef<HTMLDivElement | null>(null);
  const [browserWidthPx, setBrowserWidthPx] = React.useState(100);
  const thumbWidthPx = rowHeightPx;
  // Try to pack as many squarish thumbnails per row when in gallery mode.
  const itemsPerRow = inGalleryMode ? Math.max(1, Math.round(browserWidthPx / thumbWidthPx)) : 1;

  React.useEffect(() => {
    if (parentRef.current == null) {
      return;
    }
    const observer = new ResizeObserver((entries) => {
      const browserWidthPx = entries[0].contentRect.width;
      setBrowserWidthPx(browserWidthPx);
    });
    observer.observe(parentRef.current);
    return () => observer.disconnect();
  }, [webManifest]);

  const numVirtualRows = Math.ceil(allIds.length / itemsPerRow);
  const rowVirtualizer = useVirtualizer({
    count: hasNextPage ? numVirtualRows + 1 : numVirtualRows,
    getScrollElement: () => parentRef.current || null,
    // The estimated height of an individual item in pixels.
    estimateSize: () => rowHeightPx,
    overscan: 5,
  });
  const virtualItems = rowVirtualizer.getVirtualItems();
  const previousRowHeightPx = virtualItems[0]?.size || rowHeightPx;
  if (rowHeightPx !== previousRowHeightPx) {
    rowVirtualizer.measure();
  }

  React.useEffect(
    function maybeFetchNextPage() {
      const lastVirtualRow = rowVirtualizer.getVirtualItems().slice().reverse()[0];
      if (lastVirtualRow == null) {
        return;
      }
      if (lastVirtualRow.index >= numVirtualRows && hasNextPage && !isFetchingNextPage) {
        fetchNextPage();
      }
    },
    [hasNextPage, fetchNextPage, numVirtualRows, isFetchingNextPage, rowVirtualizer]
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
  const columns = previewPaths.map((path, i) => {
    let className = 'grow w-full truncate px-2 font-medium';
    if (i > 0) {
      className += ' border-l';
    }
    return (
      <div key={serializePath(path)} className={className}>
        {renderPath(path)}
      </div>
    );
  });
  return (
    <div className="flex h-full w-full flex-col">
      <div className="mb-4">
        <BrowserMenu
          namespace={namespace}
          datasetName={datasetName}
          schema={schema}
          previewPaths={previewPaths}
          rowHeightListPx={rowHeightListPx}
        ></BrowserMenu>
      </div>
      <div className="flex overflow-y-scroll border-b py-2">{columns}</div>
      <div ref={parentRef} className="h-full w-full overflow-y-scroll">
        <div
          style={{
            height: `${rowVirtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative',
          }}
        >
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
            const isLoaderRow = virtualRow.index >= numVirtualRows;
            const startIndex = virtualRow.index * itemsPerRow;
            const endIndex = (virtualRow.index + 1) * itemsPerRow;
            const itemIds = allIds.slice(startIndex, endIndex);

            return (
              <div
                key={virtualRow.index}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                {isLoaderRow ? (
                  'Loading more...'
                ) : (
                  <BrowserRow
                    namespace={namespace}
                    datasetName={datasetName}
                    itemIds={itemIds}
                    previewPaths={previewPaths!}
                  ></BrowserRow>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
});
