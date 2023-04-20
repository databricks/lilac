import {SlOption, SlSelect} from '@shoelace-style/shoelace/dist/react';
import {useVirtualizer} from '@tanstack/react-virtual';
import * as React from 'react';
import {Field, StatsResult, WebManifest} from '../../fastapi_client';
import {useAppDispatch, useAppSelector} from '../hooks';
import {Path, Schema, serializePath} from '../schema';
import {useGetManifestQuery, useGetMultipleStatsQuery} from '../store/api_dataset';
import {setSelectedMediaPaths, setSelectedMetadataPaths, useGetIds} from '../store/store';
import {renderPath} from '../utils';
import {GalleryItem} from './gallery_item';
import styles from './gallery_view.module.css';

export interface GalleryProps {
  namespace: string;
  datasetName: string;
}

/** Number of items to be fetched when fetching the next page. */
const ITEMS_PAGE_SIZE = 40;
/** The average item width in pixels. Multiple items can share the row if there is enough width. */
const AVG_ITEM_WIDTH_PX = 500;
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
  mediaPaths: Path[];
  metadataPaths?: Path[];
}

// TODO(smilkov): Remove this once we make a logical image dtype.
export const IMAGE_PATH_PREFIX = '__image__';

export const GalleryMenu = React.memo(function GalleryMenu({
  schema,
  mediaPaths,
  metadataPaths,
}: GalleryMenuProps): JSX.Element {
  const dispatch = useAppDispatch();

  const mediaLeafs: [Path, Field][] = [...schema.leafs].filter(([, field]) => {
    if (field.dtype === 'string' || field.dtype === 'string_span') {
      return true;
    }
    return false;
  });
  const leafs = [...schema.leafs];
  return (
    <div className="flex h-16 gap-x-4">
      {/* Media dropdown. */}
      <FeatureDropdown
        label="Media to preview"
        selectedPaths={mediaPaths}
        leafs={mediaLeafs}
        onSelectedPathsChanged={(paths) => dispatch(setSelectedMediaPaths(paths))}
      />
      {/* Metadata dropdown. */}
      <FeatureDropdown
        label="Metadata to preview"
        selectedPaths={metadataPaths}
        leafs={leafs}
        onSelectedPathsChanged={(paths) => dispatch(setSelectedMetadataPaths(paths))}
      />
    </div>
  );
});

interface FeatureDropdownProps {
  label: string;
  selectedPaths?: Path[];
  onSelectedPathsChanged: (paths: Path[]) => void;
  leafs: [Path, Field][];
}

function FeatureDropdown({
  label,
  selectedPaths,
  leafs,
  onSelectedPathsChanged,
}: FeatureDropdownProps): JSX.Element {
  selectedPaths = selectedPaths || [];
  const selectedPathsSet = new Set(selectedPaths.map((p) => serializePath(p)));
  const selectedIndices: string[] = [];
  let index = 0;
  for (const [path] of leafs) {
    if (selectedPathsSet.has(serializePath(path))) {
      selectedIndices.push(index.toString());
    }
    index++;
  }

  function onSelectedIndicesChanged(indices: string[]) {
    if (indices === selectedIndices) {
      // Avoids an infinite loop (bug in Shoelace select component) where setting the value
      // declaratively below leads to firing onChange.
      return;
    }
    const paths = indices.map((index) => leafs[Number(index)][0]);
    onSelectedPathsChanged(paths);
  }

  return (
    <div className="flex w-96 flex-col">
      <label className="text-sm font-light">{label}</label>
      <div className="flex h-full items-center">
        <SlSelect
          className={`w-full ${styles.gallery_preview_dropdown}`}
          size="small"
          value={selectedIndices}
          placeholder="Select features..."
          multiple
          maxOptionsVisible={2}
          hoist={true}
          onSlChange={(e) =>
            onSelectedIndicesChanged((e.target as HTMLInputElement).value as unknown as string[])
          }
        >
          {leafs.map(([path], i) => {
            return (
              <SlOption key={i} value={i.toString()}>
                {renderPath(path)}
              </SlOption>
            );
          })}
        </SlSelect>
      </div>
    </div>
  );
}

export interface GalleryRowProps {
  /** List of run ids to render in a single row. */
  namespace: string;
  datasetName: string;
  itemIds: string[];
  mediaPaths: Path[];
  metadataPaths?: Path[];
}

export const GalleryRow = React.memo(function GalleryRow({
  namespace,
  datasetName,
  itemIds,
  mediaPaths,
  metadataPaths,
}: GalleryRowProps): JSX.Element {
  const hundredPerc = 100;
  const widthPerc = (hundredPerc / itemIds.length).toFixed(2);
  const galleryItems = itemIds.map((itemId) => {
    return (
      <div key={itemId} style={{width: `${widthPerc}%`}}>
        <GalleryItem
          namespace={namespace}
          datasetName={datasetName}
          itemId={itemId}
          mediaPaths={mediaPaths}
          metadataPaths={metadataPaths}
        ></GalleryItem>
      </div>
    );
  });
  return <div className="flex h-full w-full shrink gap-x-4">{galleryItems}</div>;
});

export function useMediaPaths(
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
  let mediaPaths = useAppSelector((state) => state.app.selectedData.browser.selectedMediaPaths);
  const multipleStats = useGetMultipleStatsQuery({namespace, datasetName, leafPaths: stringLeafs});
  mediaPaths = React.useMemo(() => {
    if (mediaPaths != null) {
      return mediaPaths;
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
  }, [manifest, mediaPaths, multipleStats.currentData]);
  return mediaPaths;
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
  const mediaPaths = useMediaPaths(namespace, datasetName, webManifest, schema);
  const metadataPaths = useAppSelector(
    (state) => state.app.selectedData.browser.selectedMetadataPaths
  );

  const {error, isFetchingNextPage, allIds, hasNextPage, fetchNextPage} = useInfiniteItemsQuery(
    namespace,
    datasetName
  );
  // `useVirtualizer needs a reference to the scrolling element below.
  const parentRef = React.useRef<HTMLDivElement | null>(null);
  const [itemsPerRow, setItemsPerRow] = React.useState(1);
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
        const itemsPerRow = Math.max(1, Math.round(galleryWidthPx / AVG_ITEM_WIDTH_PX));
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
      <div className="border-b border-gray-200 px-4 py-2">
        <GalleryMenu
          schema={schema}
          mediaPaths={mediaPaths}
          metadataPaths={metadataPaths}
        ></GalleryMenu>
      </div>
      <div ref={parentRef} className="h-full w-full overflow-y-scroll p-4">
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
                  className="w-full"
                >
                  {isLoaderRow ? (
                    <div className={styles.loader_row}>Loading more...</div>
                  ) : (
                    <GalleryRow
                      namespace={namespace}
                      datasetName={datasetName}
                      itemIds={itemIds}
                      mediaPaths={mediaPaths}
                      metadataPaths={metadataPaths}
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
