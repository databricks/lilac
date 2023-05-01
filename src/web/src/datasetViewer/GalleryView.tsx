import {SlIcon, SlOption, SlSelect, SlTag, SlTooltip} from '@shoelace-style/shoelace/dist/react';
import {useVirtualizer} from '@tanstack/react-virtual';
import * as React from 'react';
import {Field, Filter, StatsResult, WebManifest} from '../../fastapi_client';
import {useAppDispatch} from '../hooks';
import {useGetIds} from '../hooks/useGetIds';
import {Path, Schema, serializePath} from '../schema';
import {useGetManifestQuery, useGetMultipleStatsQuery} from '../store/apiDataset';
import {
  setActiveConcept,
  setSelectedMediaPaths,
  setSelectedMetadataPaths,
  setSort,
  useDataset,
} from '../store/store';
import {renderPath} from '../utils';
import {GalleryItem} from './GalleryItem';
import styles from './GalleryView.module.css';

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
  const sort = useDataset().browser.sort;
  const [prevIds, setPrevIds] = React.useState<{[datasetId: string]: string[]}>({});
  const filters: Filter[] = [];
  const activeConcept = useDataset().activeConcept;
  const cacheKey = JSON.stringify({namespace, datasetName, filters, activeConcept, sort});
  const cachedIds = prevIds[cacheKey] || [];
  const {error, isFetching, ids} = useGetIds({
    namespace,
    datasetName,
    filters,
    activeConcept,
    limit: ITEMS_PAGE_SIZE,
    offset: cachedIds.length,
    sortBy: sort?.by,
    sortOrder: sort?.order,
  });
  const allIds = cachedIds.concat(ids || []);
  const hasNextPage = ids == null || ids.length === ITEMS_PAGE_SIZE;

  function fetchNextPage() {
    // Remember the previous ids. Key by `datasetId` so that we invalidate when the dataset changes.
    setPrevIds({[cacheKey]: allIds});
  }

  return {
    allIds,
    error,
    isFetchingNextPage: isFetching,
    hasNextPage,
    fetchNextPage,
  };
}

interface GalleryMenuProps {
  namespace: string;
  datasetName: string;
  schema: Schema;
  mediaPaths: Path[];
  metadataPaths?: Path[];
}

// TODO(smilkov): Remove this once we make a logical image dtype.
export const IMAGE_PATH_PREFIX = '__image__';

const GalleryMenu = React.memo(function GalleryMenu({
  namespace,
  datasetName,
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
    <div className="flex w-full flex-wrap gap-x-4 ">
      <div className="flex max-w-full gap-x-4">
        {/* Media dropdown. */}
        <FeatureDropdown
          label="Media to preview"
          selectedPaths={mediaPaths}
          leafs={mediaLeafs}
          onSelectedPathsChanged={(paths) =>
            dispatch(setSelectedMediaPaths({namespace, datasetName, paths}))
          }
        />
        {/* Metadata dropdown. */}
        <FeatureDropdown
          label="Metadata to preview"
          selectedPaths={metadataPaths}
          leafs={leafs}
          onSelectedPathsChanged={(paths) =>
            dispatch(setSelectedMetadataPaths({namespace, datasetName, paths}))
          }
        />
      </div>
      <div className="flex max-w-full gap-x-4 ">
        <ActiveConceptLegend namespace={namespace} datasetName={datasetName}></ActiveConceptLegend>
        <SortMenu namespace={namespace} datasetName={datasetName}></SortMenu>
      </div>
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
      <label className="text-sm font-light text-gray-400">{label}</label>
      <div className="flex items-center">
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

function ActiveConceptLegend({
  namespace,
  datasetName,
}: {
  namespace: string;
  datasetName: string;
}): JSX.Element {
  const dispatch = useAppDispatch();

  const activeConcept = useDataset().activeConcept;
  return (
    <div className={`relative my-auto py-2 text-xs`}>
      {activeConcept == null ? (
        <div className="text-sm font-light text-gray-400">No active concept.</div>
      ) : (
        <div className="font-light">
          <div className="mb-1">Active concept</div>
          <SlTooltip
            content={
              `Active concept "${activeConcept.concept.name}" with ` +
              `embedding "${activeConcept.embedding.name}" ` +
              `over column "${renderPath(activeConcept.column)}".`
            }
          >
            <SlTag
              size="medium"
              pill
              removable
              onSlRemove={() =>
                dispatch(setActiveConcept({namespace, datasetName, activeConcept: null}))
              }
            >
              <div className="flex flex-row">
                <div className={`flex w-5 items-center ${styles.sort_icon}`}>
                  <SlIcon name="stars"></SlIcon>
                </div>
                <div>{activeConcept.concept.name}</div>
              </div>
            </SlTag>
          </SlTooltip>
        </div>
      )}
    </div>
  );
}

function SortMenu({namespace, datasetName}: {namespace: string; datasetName: string}): JSX.Element {
  const dispatch = useAppDispatch();

  const sort = useDataset().browser.sort;
  const sortByDisplay = sort?.by.map((p) => renderPath(p)).join(' > ');
  return (
    <div className="my-auto flex py-2">
      {sort == null ? (
        <div className="text-sm font-light text-gray-400">No active sort.</div>
      ) : (
        <div className="flex flex-col font-light">
          <div className="mb-1">Sorted by</div>
          <div>
            <SlTooltip content={`Sorted by "${sortByDisplay}" ${sort.order}.`}>
              <SlTag
                size="medium"
                pill
                removable
                onSlRemove={() => dispatch(setSort({namespace, datasetName, sort: null}))}
              >
                <div className="flex flex-row">
                  <div className={`flex w-5 items-center ${styles.sort_icon}`}>
                    <SlIcon name={sort.order === 'DESC' ? 'sort-down' : 'sort-up'}></SlIcon>
                  </div>
                  <div>{sortByDisplay}</div>
                </div>
              </SlTag>
            </SlTooltip>
          </div>
        </div>
      )}
    </div>
  );
}

export function useMediaPaths(
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

  let mediaPaths = useDataset().browser.selectedMediaPaths;
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
  }, [manifest, mediaPaths, multipleStats.currentData, stringLeafs]);
  return mediaPaths;
}

export const GalleryView = React.memo(function Gallery({
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
  const metadataPaths = useDataset().browser.selectedMetadataPaths;

  const {error, isFetchingNextPage, allIds, hasNextPage, fetchNextPage} = useInfiniteItemsQuery(
    namespace,
    datasetName
  );
  // `useVirtualizer needs a reference to the scrolling element below.
  const parentRef = React.useRef<HTMLDivElement | null>(null);
  const numRows = allIds.length;

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
    [hasNextPage, fetchNextPage, numRows, isFetchingNextPage, virtualizer]
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
          namespace={namespace}
          datasetName={datasetName}
          schema={schema}
          mediaPaths={mediaPaths}
          metadataPaths={metadataPaths}
        ></GalleryMenu>
      </div>
      <div ref={parentRef} className="h-full w-full overflow-y-scroll">
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

              const itemId = allIds[virtualRow.index];

              return (
                <div
                  key={virtualRow.index}
                  data-index={virtualRow.index}
                  ref={virtualizer.measureElement}
                  className="w-full border-b"
                >
                  {isLoaderRow ? (
                    <div className={styles.loader_row}>Loading more...</div>
                  ) : (
                    <GalleryItem
                      itemId={itemId}
                      namespace={namespace}
                      datasetName={datasetName}
                      mediaPaths={mediaPaths}
                      metadataPaths={metadataPaths}
                    ></GalleryItem>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <div className="border-t px-4 py-1 text-sm font-light text-gray-500">
        Showing rows {virtualizer.range.startIndex.toLocaleString()} -{' '}
        {virtualizer.range.endIndex.toLocaleString()}
      </div>
    </div>
  );
});
