import {
  SlAlert,
  SlBreadcrumb,
  SlBreadcrumbItem,
  SlButton,
  SlIcon,
  SlSpinner,
} from '@shoelace-style/shoelace/dist/react';
import {Command} from 'cmdk';
import * as React from 'react';
import {Location, useLocation, useNavigate, useParams} from 'react-router-dom';
import {ConceptInfo, EmbeddingInfo, Field, SignalInfo} from '../../fastapi_client';
import {useAppDispatch} from '../hooks';
import {Path, Schema, serializePath} from '../schema';
import {
  useComputeEmbeddingIndexMutation,
  useComputeSignalColumnMutation,
  useGetDatasetsQuery,
  useGetManifestQuery,
  useGetStatsQuery,
} from '../store/api_dataset';
import {setActiveConcept, setTasksPanelOpen, useTopValues} from '../store/store';
import {renderPath, renderQuery, useClickOutside} from '../utils';
import {ColumnSelector} from './column_selector';
import {ConceptSelector} from './concept_selector';
import {EmbeddingSelector} from './embedding_selector';
import {Item} from './item_selector';
import './search_box.css';
import {SignalSelector} from './signal_selector';

/** Time to debounce (ms). */
const DEBOUNCE_TIME_MS = 100;

type PageType = keyof PageMetadata;
interface PageMetadata {
  'open-dataset': Record<string, never>;
  'add-filter': Record<string, never>;
  'add-filter-value': {path: Path; field: Field};
  'compute-signal': Record<string, never>;
  'compute-signal-column': {signal: SignalInfo};
  'compute-embedding-index': Record<string, never>;
  'compute-embedding-index-column': {embedding: EmbeddingInfo};
  'compute-embedding-index-accept': {embedding: EmbeddingInfo; column: Path};
  'edit-concept': Record<string, never>;
  'edit-concept-embedding': {concept: ConceptInfo};
  'edit-concept-column': {concept: ConceptInfo; embedding: EmbeddingInfo};
  'edit-concept-accept': {
    concept: ConceptInfo;
    embedding: EmbeddingInfo;
    column: Path;
    description: string;
  };
}

const PAGE_SEARCH_TITLE: Record<PageType, string> = {
  'open-dataset': 'Select a dataset',
  'add-filter': 'Add filter',
  'add-filter-value': 'Add filter value',
  'compute-signal': 'compute signal',
  'compute-signal-column': 'compute signal',
  'compute-embedding-index': 'select embedding',
  'compute-embedding-index-column': 'select column',
  'compute-embedding-index-accept': '',
  'edit-concept': 'select concept',
  'edit-concept-embedding': 'select embedding',
  'edit-concept-column': 'select column',
  'edit-concept-accept': '',
};

// TODO(nsthorat): Add the icon to the metadata so we can use it from breadcrumbs
// TODO(nsthorat): When selecting a column for embeddings, have 2 sections one for ones that
// have been computed, ones that haven't.

interface Page<T extends PageType = PageType> {
  type: T;
  name: string;
  metadata?: PageMetadata[T];
}

export const SearchBox = () => {
  const dispatch = useAppDispatch();

  const ref = React.useRef<HTMLDivElement | null>(null);
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const [inputValue, setInputValue] = React.useState('');
  const [isFocused, setIsFocused] = React.useState(false);
  const [pages, setPages] = React.useState<Page[]>([]);
  const location = useLocation();
  const {namespace, datasetName} = useParams<{namespace: string; datasetName: string}>();

  /** Closes the menu. */
  const closeMenu = React.useCallback(() => {
    ref.current?.blur();
    inputRef.current?.blur();
    setPages([]);
    setIsFocused(false);
  }, []);

  const handleFocus = React.useCallback(() => {
    setIsFocused(true);
  }, []);

  useClickOutside(ref, [], () => {
    setIsFocused(false);
  });

  let activePage: Page | null = null;
  if (pages.length > 0) {
    activePage = pages[pages.length - 1];
  }
  const isHome = activePage == null;

  const popPage = React.useCallback(() => {
    setPages((pages) => {
      const x = [...pages];
      x.splice(-1, 1);
      return x;
    });
  }, []);

  const pushPage = React.useCallback((page: Page) => {
    setInputValue('');
    inputRef.current?.focus();
    setPages((pages) => [...pages, page]);
  }, []);

  function bounce() {
    if (ref.current == null) {
      return;
    }
    ref.current.style.transform = 'scale(0.985)';
    setTimeout(() => {
      if (ref.current) {
        ref.current.style.transform = '';
      }
    }, DEBOUNCE_TIME_MS);

    setInputValue('');
  }

  const [computeSignal] = useComputeSignalColumnMutation();

  return (
    <div className="w-full">
      <Command
        tabIndex={0}
        ref={ref}
        onFocus={handleFocus}
        onKeyDown={(e: React.KeyboardEvent) => {
          if (e.key === 'Enter') {
            bounce();
          }

          if (isHome) {
            return;
          }

          if (e.key === 'Escape') {
            e.preventDefault();
            popPage();
            bounce();
            return;
          }

          if (inputValue.length == 0 && e.key === 'Backspace') {
            e.preventDefault();
            popPage();
            bounce();
          }
        }}
      >
        <div className="flex flex-row items-center justify-items-center">
          {pages.length > 0 ? (
            <div className="ml-2 mr-4">
              <SlBreadcrumb>
                {pages.map((p) => (
                  <SlBreadcrumbItem key={`${p.type}_${p.name}`} className="truncate">
                    {p.name}
                  </SlBreadcrumbItem>
                ))}
              </SlBreadcrumb>
            </div>
          ) : (
            <></>
          )}
          <div className="flex-1 text-xs">
            <Command.Input
              value={inputValue}
              ref={inputRef}
              style={{flexGrow: 1}}
              placeholder={
                activePage?.type == null
                  ? 'Search and run commands'
                  : PAGE_SEARCH_TITLE[activePage?.type]
              }
              onValueChange={setInputValue}
            />
          </div>
        </div>
        <Command.List>
          {isFocused && (
            <>
              <div className="mt-2"></div>
              {activePage?.type == null && <Command.Empty>No results found.</Command.Empty>}
              {isHome && <HomeMenu pushPage={pushPage} location={location} closeMenu={closeMenu} />}
              {activePage?.type == 'open-dataset' && <Datasets closeMenu={closeMenu} />}
              {activePage?.type == 'add-filter' && <AddFilter pushPage={pushPage} />}
              {activePage?.type == 'add-filter-value' && (
                <AddFilterValue
                  inputValue={inputValue}
                  closeMenu={closeMenu}
                  page={activePage as Page<'add-filter-value'>}
                />
              )}
              {/*
                  Edit a concept.
                  Concept => Embedding => Column setup
               */}
              {activePage?.type == 'edit-concept' && (
                <ConceptSelector
                  onSelect={(concept) => {
                    pushPage({
                      type: 'edit-concept-embedding',
                      name: concept.name,
                      metadata: {concept},
                    });
                  }}
                />
              )}
              {activePage?.type == 'edit-concept-embedding' && (
                <EmbeddingSelector
                  onSelect={(embedding) => {
                    pushPage({
                      type: 'edit-concept-column',
                      name: embedding.name,
                      metadata: {
                        concept: (activePage as Page<'edit-concept-embedding'>)?.metadata?.concept,
                        embedding,
                      },
                    });
                  }}
                />
              )}
              {activePage?.type == 'edit-concept-column' && (
                <ColumnSelector
                  leafFilter={(leaf, embeddings) => {
                    const hasEmbedding =
                      embeddings == null
                        ? false
                        : embeddings.includes(
                            (activePage as Page<'edit-concept-column'>).metadata!.embedding.name
                          );
                    return hasEmbedding;
                  }}
                  enrichmentType="text"
                  onSelect={(path) => {
                    dispatch(
                      setActiveConcept({
                        concept: (activePage as Page<'edit-concept-column'>).metadata!.concept,
                        embedding: (activePage as Page<'edit-concept-column'>).metadata!.embedding,
                        column: path,
                      })
                    );
                    closeMenu();
                  }}
                ></ColumnSelector>
              )}
              {activePage?.type == 'compute-signal' && (
                <SignalSelector
                  onSelect={(signal) => {
                    pushPage({
                      type: 'compute-signal-column',
                      name: signal.name,
                      metadata: {signal},
                    });
                  }}
                />
              )}
              {activePage?.type == 'compute-signal-column' && (
                <ColumnSelector
                  leafFilter={() => {
                    // TODO(nsthorat): Use the embedding_based bit to determine the filter for
                    // leafs. We should also determine whether to compute embeddings automatically
                    // at this stage.
                    return true;
                  }}
                  enrichmentType={
                    (activePage as Page<'compute-signal-column'>).metadata!.signal.enrichment_type
                  }
                  onSelect={async (path) => {
                    const signal = (activePage as Page<'compute-signal-column'>).metadata!.signal;
                    await computeSignal({
                      namespace: namespace!,
                      datasetName: datasetName!,
                      options: {leaf_path: path, signal: {signal_name: signal.name}},
                    });
                    dispatch(setTasksPanelOpen(true));
                    closeMenu();
                  }}
                ></ColumnSelector>
              )}
              {activePage?.type == 'compute-embedding-index' && (
                <EmbeddingSelector
                  onSelect={(embedding) => {
                    pushPage({
                      type: 'compute-embedding-index-column',
                      name: embedding.name,
                      metadata: {embedding},
                    });
                  }}
                />
              )}
              {activePage?.type == 'compute-embedding-index-column' && (
                <ColumnSelector
                  leafFilter={() => true}
                  enrichmentType="text"
                  onSelect={(path) => {
                    pushPage({
                      type: 'compute-embedding-index-accept',
                      name: renderPath(path),
                      metadata: {
                        embedding: (activePage as Page<'compute-embedding-index-column'>).metadata!
                          .embedding,
                        column: path,
                        description: '',
                      },
                    });
                  }}
                ></ColumnSelector>
              )}
              {activePage?.type == 'compute-embedding-index-accept' && (
                <ComputeEmbeddingIndexAccept
                  closeMenu={closeMenu}
                  page={activePage as Page<'compute-embedding-index-accept'>}
                />
              )}
            </>
          )}
        </Command.List>
      </Command>
    </div>
  );
};

function HomeMenu({
  pushPage,
  location,
  closeMenu,
}: {
  pushPage: (page: Page) => void;
  location: Location;
  closeMenu: () => void;
}) {
  const navigate = useNavigate();
  const datasetSelected = location.pathname.startsWith('/datasets/');
  return (
    <>
      {/* Filtering */}
      {datasetSelected && (
        <Command.Group heading="Filters">
          <Item onSelect={() => pushPage({type: 'add-filter', name: 'Add filter'})}>
            <SlIcon className="text-xl" name="database" />
            Add filter
          </Item>
          <Item>
            <SlIcon className="text-xl" name="database" />
            Remove filter
          </Item>
        </Command.Group>
      )}

      {/* Signals */}
      {datasetSelected && (
        <Command.Group heading="Signals">
          <Item
            onSelect={() => {
              pushPage({type: 'compute-signal', name: 'Compute signal'});
            }}
          >
            <SlIcon className="text-xl" name="magic" />
            Compute signal
          </Item>
          <Item
            onSelect={() => {
              pushPage({type: 'compute-embedding-index', name: 'compute embeddings'});
            }}
          >
            <SlIcon className="text-xl" name="cpu" />
            Compute embeddings
          </Item>
        </Command.Group>
      )}

      {/* Concepts */}
      <Command.Group heading="Concepts">
        <Item
          onSelect={() => {
            pushPage({type: 'edit-concept', name: 'Edit concept'});
          }}
        >
          <SlIcon className="text-xl" name="stars" />
          Edit concept
        </Item>
        <Item>
          <SlIcon className="text-xl" name="plus-lg" />
          Create new concept
        </Item>
      </Command.Group>

      {/* Datasets */}
      <Command.Group heading="Datasets">
        <Item
          onSelect={() => {
            pushPage({type: 'open-dataset', name: 'Open dataset'});
          }}
        >
          <SlIcon className="text-xl" name="database" />
          Open dataset
        </Item>
        <Item
          onSelect={() => {
            closeMenu();
            navigate(`/dataset_loader`);
          }}
        >
          <SlIcon className="text-xl" name="database-add" />
          Create new dataset
        </Item>
      </Command.Group>

      {/* Help */}
      <Command.Group heading="Help">
        <Item>
          <SlIcon className="text-xl" name="file-earmark-text" />
          Search Docs...
        </Item>
        <Item>
          <SlIcon className="text-xl" name="github" />
          Create a GitHub issue
        </Item>
        <Item>
          <SlIcon className="text-xl" name="envelope" />
          Contact us
        </Item>
      </Command.Group>
    </>
  );
}

function Datasets({closeMenu}: {closeMenu: () => void}) {
  const query = useGetDatasetsQuery();
  const navigate = useNavigate();

  return renderQuery(query, (datasets) => (
    <>
      {datasets.map((d) => {
        const key = `${d.namespace}/${d.dataset_name}`;
        return (
          <Item
            key={key}
            onSelect={() => {
              closeMenu();
              navigate(`/datasets/${d.namespace}/${d.dataset_name}`);
            }}
          >
            {d.namespace} / {d.dataset_name}
          </Item>
        );
      })}
    </>
  ));
}

function AddFilterValue({
  closeMenu,
  inputValue,
  page,
}: {
  inputValue: string;
  closeMenu: () => void;
  page: Page<'add-filter-value'>;
}) {
  const {namespace, datasetName} = useParams<{namespace: string; datasetName: string}>();
  if (namespace == null || datasetName == null) {
    throw new Error('Invalid route');
  }
  const leafPath = page.metadata!.path;
  const field = page.metadata!.field;
  const topK = 100;
  const {isFetching, tooManyDistinct, onlyTopK, values, dtypeNotSupported, statsResult} =
    useTopValues({namespace, datasetName, leafPath, field, topK, vocabOnly: true});
  const vocab = values.map(([v]) => v);

  if (isFetching) {
    return <SlSpinner />;
  }

  // Add the current input value to the list of values, and wrap it in quotes.
  if (inputValue.length > 0) {
    vocab.unshift(`"${inputValue}"`);
  }

  const items = vocab.map((value, i) => {
    return (
      <Item
        key={i}
        onSelect={() => {
          closeMenu();
          // TODO(smilkov): Add the filter to the app state.
        }}
      >
        {value ? value.toString() : 'N/A'}
      </Item>
    );
  });
  return (
    <>
      {onlyTopK && <Item disabled>Showing only the top {topK} values...</Item>}
      {items}
      {tooManyDistinct && (
        <Item disabled>
          Too many distinct values ({statsResult?.approx_count_distinct.toLocaleString()}) to
          list...
        </Item>
      )}
      {dtypeNotSupported && <Item disabled>Dtype {field.dtype} is not supported...</Item>}
    </>
  );
}

function AddFilter({pushPage}: {pushPage: (page: Page) => void}) {
  const {namespace, datasetName} = useParams<{namespace: string; datasetName: string}>();
  if (namespace == null || datasetName == null) {
    throw new Error('Invalid route');
  }
  const {isFetching, currentData: webManifest} = useGetManifestQuery({namespace, datasetName});
  if (isFetching || webManifest == null) {
    return <SlSpinner />;
  }
  const schema = new Schema(webManifest.dataset_manifest.data_schema);
  const items = schema.leafs.map(([path, field]) => {
    const pathKey = serializePath(path);
    const pathStr = renderPath(path);
    return (
      <Item
        key={pathKey}
        onSelect={() => {
          pushPage({type: 'add-filter-value', name: pathStr, metadata: {path, field}});
        }}
      >
        {pathStr}
      </Item>
    );
  });
  return <>{items}</>;
}

function ComputeEmbeddingIndexAccept({
  page,
  closeMenu,
}: {
  page: Page<'compute-embedding-index-accept'>;
  closeMenu: () => void;
}) {
  const {namespace, datasetName} = useParams<{namespace: string; datasetName: string}>();
  if (namespace == null || datasetName == null) {
    throw new Error('Invalid route');
  }
  const dispatch = useAppDispatch();

  const [computeEmbedding, {isLoading: isComputeEmbeddingLoading}] =
    useComputeEmbeddingIndexMutation();

  const query = useGetStatsQuery({
    namespace,
    datasetName,
    options: {leaf_path: page.metadata!.column!},
  });

  return renderQuery(query, (stats) => {
    const path = renderPath(page.metadata!.column!);
    return (
      <>
        <SlAlert open variant="warning">
          <SlIcon slot="icon" name="exclamation-triangle" />
          <div className="flex flex-col">
            <div className="font-semibold">
              You are about to compute embeddings with "{page.metadata!.embedding!.name}" over the
              column "{path}".
            </div>
            <div className="mt-2 text-xs">
              "{path}" consists of {stats.total_count.toLocaleString()} documents with ~
              {Math.round(stats.avg_text_length!)} characters on average.
            </div>
            <div className="mt-2 text-xs">
              This may be expensive! For some embeddings, this will send data to a server.
            </div>
          </div>
        </SlAlert>
        <div className="mt-2"></div>
        <div>
          <SlButton
            variant="primary"
            outline
            className="mr-0 w-48"
            onClick={async () => {
              // Compute the embedding, and pop the user over to the tasks panel.
              await computeEmbedding({
                namespace,
                datasetName,
                options: {
                  leaf_path: page.metadata!.column!,
                  embedding: {embedding_name: page.metadata?.embedding.name},
                },
              }).unwrap();
              dispatch(setTasksPanelOpen(true));
              closeMenu();
            }}
          >
            <div className="flex flex-row items-center justify-items-center">
              {!isComputeEmbeddingLoading ? (
                <SlIcon slot="prefix" name="cpu" className="mr-1"></SlIcon>
              ) : (
                <SlSpinner></SlSpinner>
              )}
              Compute embeddings
            </div>
          </SlButton>
        </div>
      </>
    );
  });
}
