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
import {ConceptInfo, EmbeddingInfo, Field, SignalInfo, SortOrder} from '../../fastapi_client';
import {useAppDispatch, useAppSelector} from '../hooks';
import {useTopValues} from '../hooks/useTopValues';
import {Path} from '../schema';
import {
  useComputeSignalColumnMutation,
  useGetDatasetsQuery,
  useGetStatsQuery,
} from '../store/apiDataset';
import {
  popSearchBoxPage,
  pushSearchBoxPage,
  setActiveConcept,
  setSearchBoxOpen,
  setSearchBoxPages,
  setSort,
  setTasksPanelOpen,
} from '../store/store';
import {renderPath, renderQuery, useClickOutside} from '../utils';
import {ColumnSelector} from './ColumnSelector';
import {ConceptSelector} from './ConceptSelector';
import {EmbeddingSelector} from './EmbeddingSelector';
import './SearchBox.css';
import {SearchBoxItem} from './SearchBoxItem';
import {SignalSelector} from './SignalSelector';

/** Time to debounce (ms). */
const DEBOUNCE_TIME_MS = 100;

type PageType = keyof SearchBoxPageMetadata;
export interface SearchBoxPageMetadata {
  'open-dataset': Record<string, never>;
  'add-filter': Record<string, never>;
  'add-filter-value': {path: Path; field: Field};
  'sort-by': Record<string, never>;
  'sort-by-order': {path: Path; field: Field};
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
  'add-filter': 'select column',
  'add-filter-value': 'select value',
  'sort-by': 'select column',
  'sort-by-order': 'select order',
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

export interface SearchBoxPage<T extends PageType = PageType> {
  type: T;
  name: string;
  metadata?: SearchBoxPageMetadata[T];
}

export const SearchBox = () => {
  const dispatch = useAppDispatch();

  const ref = React.useRef<HTMLDivElement | null>(null);
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const wasOpen = React.useRef(false);
  const [inputValue, setInputValue] = React.useState('');
  const searchBoxOpen = useAppSelector((state) => state.app.searchBoxOpen);
  const pages = useAppSelector((state) => state.app.searchBoxPages);
  const location = useLocation();
  const {namespace, datasetName} = useParams<{namespace: string; datasetName: string}>();

  // Check if search box is open, but lacks focus
  React.useEffect(() => {
    if (searchBoxOpen && !wasOpen.current) {
      inputRef.current?.focus();
      wasOpen.current = true;
    } else if (!searchBoxOpen) {
      wasOpen.current = false;
    }
  }, [searchBoxOpen, wasOpen]);

  /** Closes the menu. */
  const closeMenu = React.useCallback(() => {
    ref.current?.blur();
    inputRef.current?.blur();
    dispatch(setSearchBoxPages([]));
    dispatch(setSearchBoxOpen(false));
  }, [dispatch]);

  const handleFocus = React.useCallback(() => {
    if (!searchBoxOpen) {
      dispatch(setSearchBoxOpen(true));
    }
  }, [dispatch, searchBoxOpen]);

  useClickOutside(ref, [], () => {
    dispatch(setSearchBoxOpen(false));
  });

  let activePage: SearchBoxPage | null = null;
  if (pages.length > 0) {
    activePage = pages[pages.length - 1];
  }
  const isHome = activePage == null;

  const popPage = React.useCallback(() => {
    dispatch(popSearchBoxPage());
  }, [dispatch]);

  const pushPage = React.useCallback(
    (page: SearchBoxPage) => {
      setInputValue('');
      inputRef.current?.focus();
      dispatch(pushSearchBoxPage(page));
    },
    [dispatch]
  );

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
          {searchBoxOpen && (
            <>
              <div className="mt-2"></div>
              {activePage?.type == null && <Command.Empty>No results found.</Command.Empty>}
              {isHome && <HomeMenu pushPage={pushPage} location={location} closeMenu={closeMenu} />}
              {activePage?.type == 'open-dataset' && <Datasets closeMenu={closeMenu} />}
              {activePage?.type == 'add-filter' && (
                <ColumnSelector
                  onSelect={(path, field) => {
                    pushPage({
                      type: 'add-filter-value',
                      name: renderPath(path),
                      metadata: {path, field},
                    });
                  }}
                ></ColumnSelector>
              )}
              {activePage?.type == 'add-filter-value' && (
                <AddFilterValue
                  inputValue={inputValue}
                  closeMenu={closeMenu}
                  page={activePage as SearchBoxPage<'add-filter-value'>}
                />
              )}
              {/* Viewer controls */}
              {activePage?.type == 'sort-by' && (
                <ColumnSelector
                  onSelect={(path, field) => {
                    pushPage({
                      type: 'sort-by-order',
                      name: renderPath(path),
                      metadata: {path, field},
                    });
                  }}
                ></ColumnSelector>
              )}
              {activePage?.type == 'sort-by-order' && (
                <SortByOrder
                  onSelect={(order) => {
                    const by = (activePage as SearchBoxPage<'sort-by-order'>).metadata!.path;
                    dispatch(
                      setSort({
                        namespace: namespace!,
                        datasetName: datasetName!,
                        sort: {by: [by], order},
                      })
                    );
                    closeMenu();
                  }}
                ></SortByOrder>
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
                        concept: (activePage as SearchBoxPage<'edit-concept-embedding'>)?.metadata
                          ?.concept,
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
                            (activePage as SearchBoxPage<'edit-concept-column'>).metadata!.embedding
                              .name
                          );
                    return hasEmbedding;
                  }}
                  inputType="text"
                  onSelect={(path) => {
                    dispatch(
                      setActiveConcept({
                        namespace: namespace!,
                        datasetName: datasetName!,
                        activeConcept: {
                          concept: (activePage as SearchBoxPage<'edit-concept-column'>).metadata!
                            .concept,
                          embedding: (activePage as SearchBoxPage<'edit-concept-column'>).metadata!
                            .embedding,
                          column: path,
                        },
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
                    // TODO(nsthorat): Use the vector_based bit to determine the filter for
                    // leafs. We should also determine whether to compute embeddings automatically
                    // at this stage.
                    return true;
                  }}
                  inputType={
                    (activePage as SearchBoxPage<'compute-signal-column'>).metadata!.signal
                      .input_type
                  }
                  onSelect={async (path) => {
                    const signal = (activePage as SearchBoxPage<'compute-signal-column'>).metadata!
                      .signal;
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
                  inputType="text"
                  onSelect={(path) => {
                    pushPage({
                      type: 'compute-embedding-index-accept',
                      name: renderPath(path),
                      metadata: {
                        embedding: (activePage as SearchBoxPage<'compute-embedding-index-column'>)
                          .metadata!.embedding,
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
                  page={activePage as SearchBoxPage<'compute-embedding-index-accept'>}
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
  pushPage: (page: SearchBoxPage) => void;
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
          <SearchBoxItem onSelect={() => pushPage({type: 'add-filter', name: 'Add filter'})}>
            <SlIcon className="text-xl" name="database" />
            Add filter
          </SearchBoxItem>
          <SearchBoxItem>
            <SlIcon className="text-xl" name="database" />
            Remove filter
          </SearchBoxItem>
        </Command.Group>
      )}

      {/* Viewer controls */}
      {datasetSelected && (
        <Command.Group heading="Viewer">
          <SearchBoxItem onSelect={() => pushPage({type: 'sort-by', name: 'Sort by'})}>
            <SlIcon className="text-xl" name="sort-down" />
            Sort by
          </SearchBoxItem>
        </Command.Group>
      )}

      {/* Signals */}
      {datasetSelected && (
        <Command.Group heading="Signals">
          <SearchBoxItem
            onSelect={() => {
              pushPage({type: 'compute-signal', name: 'Compute signal'});
            }}
          >
            <SlIcon className="text-xl" name="magic" />
            Compute signal
          </SearchBoxItem>
          <SearchBoxItem
            onSelect={() => {
              pushPage({type: 'compute-embedding-index', name: 'compute embeddings'});
            }}
          >
            <SlIcon className="text-xl" name="cpu" />
            Compute embeddings
          </SearchBoxItem>
        </Command.Group>
      )}

      {/* Concepts */}
      <Command.Group heading="Concepts">
        <SearchBoxItem
          onSelect={() => {
            pushPage({type: 'edit-concept', name: 'Edit concept'});
          }}
        >
          <SlIcon className="text-xl" name="stars" />
          Edit concept
        </SearchBoxItem>
        <SearchBoxItem>
          <SlIcon className="text-xl" name="plus-lg" />
          Create new concept
        </SearchBoxItem>
      </Command.Group>

      {/* Datasets */}
      <Command.Group heading="Datasets">
        <SearchBoxItem
          onSelect={() => {
            pushPage({type: 'open-dataset', name: 'Open dataset'});
          }}
        >
          <SlIcon className="text-xl" name="database" />
          Open dataset
        </SearchBoxItem>
        <SearchBoxItem
          onSelect={() => {
            closeMenu();
            navigate(`/new`);
          }}
        >
          <SlIcon className="text-xl" name="database-add" />
          Create new dataset
        </SearchBoxItem>
      </Command.Group>

      {/* Help */}
      <Command.Group heading="Help">
        <SearchBoxItem>
          <SlIcon className="text-xl" name="file-earmark-text" />
          Search Docs...
        </SearchBoxItem>
        <SearchBoxItem>
          <SlIcon className="text-xl" name="github" />
          Create a GitHub issue
        </SearchBoxItem>
        <SearchBoxItem>
          <SlIcon className="text-xl" name="envelope" />
          Contact us
        </SearchBoxItem>
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
          <SearchBoxItem
            key={key}
            onSelect={() => {
              closeMenu();
              navigate(`/datasets/${d.namespace}/${d.dataset_name}`);
            }}
          >
            {d.namespace} / {d.dataset_name}
          </SearchBoxItem>
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
  page: SearchBoxPage<'add-filter-value'>;
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
      <SearchBoxItem
        key={i}
        onSelect={() => {
          closeMenu();
          // TODO(smilkov): Add the filter to the app state.
        }}
      >
        {value ? value.toString() : 'N/A'}
      </SearchBoxItem>
    );
  });
  return (
    <>
      {onlyTopK && <SearchBoxItem disabled>Showing only the top {topK} values...</SearchBoxItem>}
      {items}
      {tooManyDistinct && (
        <SearchBoxItem disabled>
          Too many distinct values ({statsResult?.approx_count_distinct.toLocaleString()}) to
          list...
        </SearchBoxItem>
      )}
      {dtypeNotSupported && (
        <SearchBoxItem disabled>Dtype {field.dtype} is not supported...</SearchBoxItem>
      )}
    </>
  );
}

function SortByOrder({onSelect}: {onSelect: (sortOrder: SortOrder) => void}) {
  return (
    <>
      <SearchBoxItem onSelect={() => onSelect('ASC')}>ascending</SearchBoxItem>
      <SearchBoxItem onSelect={() => onSelect('DESC')}>descending</SearchBoxItem>
    </>
  );
}

function ComputeEmbeddingIndexAccept({
  page,
  closeMenu,
}: {
  page: SearchBoxPage<'compute-embedding-index-accept'>;
  closeMenu: () => void;
}) {
  const {namespace, datasetName} = useParams<{namespace: string; datasetName: string}>();
  if (namespace == null || datasetName == null) {
    throw new Error('Invalid route');
  }
  const dispatch = useAppDispatch();

  const [computeEmbedding, {isLoading: isComputeEmbeddingLoading}] =
    useComputeSignalColumnMutation();

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
                  signal: {signal_name: page.metadata?.embedding.name},
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
