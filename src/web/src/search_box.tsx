import {
  SlAlert,
  SlBreadcrumb,
  SlBreadcrumbItem,
  SlButton,
  SlIcon,
  SlOption,
  SlSelect,
  SlSpinner,
} from '@shoelace-style/shoelace/dist/react';
import {Command} from 'cmdk';
import {JSONSchema7} from 'json-schema';
import * as React from 'react';
import {Location, useLocation, useNavigate, useParams} from 'react-router-dom';
import {ConceptInfo, EmbeddingInfo, EnrichmentType, Field, SignalInfo} from '../fastapi_client';
import {Path, Schema, serializePath} from './schema';
import './search_box.css';
import {useGetConceptsQuery} from './store/api_concept';
import {
  useComputeEmbeddingIndexMutation,
  useComputeSignalColumnMutation,
  useGetDatasetsQuery,
  useGetManifestQuery,
  useGetMultipleStatsQuery,
  useGetStatsQuery,
} from './store/api_dataset';
import {useGetEmbeddingsQuery} from './store/api_embeddings';
import {useGetSignalsQuery} from './store/api_signal';
import {useTopValues} from './store/store';
import {renderPath, renderQuery, useClickOutside} from './utils';

/** Time to debounce (ms). */
const DEBOUNCE_TIME_MS = 100;

type PageType = keyof PageMetadata;
interface PageMetadata {
  'open-dataset': Record<string, never>;
  'add-filter': Record<string, never>;
  'add-filter-value': {path: Path; field: Field};
  'compute-signal': Record<string, never>;
  'compute-signal-setup': {signal: SignalInfo};
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
  'compute-signal-setup': 'compute signal',
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
  const ref = React.useRef<HTMLDivElement | null>(null);
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const [inputValue, setInputValue] = React.useState('');
  const [isFocused, setIsFocused] = React.useState(false);
  const [pages, setPages] = React.useState<Page[]>([]);
  const location = useLocation();

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
                <Concepts
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
                <Embeddings
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
                <Columns
                  enrichmentType="text"
                  onSelect={(path) => {
                    pushPage({
                      type: 'edit-concept-accept',
                      name: renderPath(path),
                      metadata: {
                        concept: (activePage as Page<'edit-concept-column'>).metadata!.concept,
                        embedding: (activePage as Page<'edit-concept-column'>).metadata!.embedding,
                        column: path,
                        description: '',
                      },
                    });
                  }}
                ></Columns>
              )}
              {activePage?.type == 'edit-concept-accept' && (
                <EditConceptAccept
                  page={activePage as Page<'edit-concept-accept'>}
                ></EditConceptAccept>
              )}
              {activePage?.type == 'compute-signal' && <ComputeSignal pushPage={pushPage} />}
              {activePage?.type == 'compute-signal-setup' && (
                <ComputeSignalSetup page={activePage as Page<'compute-signal-setup'>} />
              )}
              {activePage?.type == 'compute-embedding-index' && (
                <Embeddings
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
                <Columns
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
                ></Columns>
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

function ComputeSignal({pushPage}: {pushPage: (page: Page) => void}) {
  const {namespace, datasetName} = useParams<{namespace: string; datasetName: string}>();
  if (namespace == null || datasetName == null) {
    throw new Error('Invalid route');
  }
  const query = useGetSignalsQuery();
  return renderQuery(query, (signals) => {
    return (
      <>
        {signals.map((signal) => {
          const jsonSchema = signal.json_schema as JSONSchema7;
          return (
            <Item
              key={signal.name}
              onSelect={() => {
                pushPage({
                  type: 'compute-signal-setup',
                  name: signal.name,
                  metadata: {signal},
                });
              }}
            >
              <div className="flex w-full justify-between">
                <div className="truncate">{signal.name}</div>
                <div className="truncate">{jsonSchema.description}</div>
              </div>
            </Item>
          );
        })}
      </>
    );
  });
}

function getLeafsByEnrichmentType(leafs: [Path, Field][], enrichmentType: EnrichmentType) {
  if (enrichmentType !== 'text') {
    throw new Error(`Unsupported enrichment type: ${enrichmentType}`);
  }
  return leafs.filter(([, field]) => {
    if (enrichmentType === 'text' && ['string', 'string_span'].includes(field.dtype!)) {
      return true;
    }
    return false;
  });
}

function ComputeSignalSetup({page}: {page: Page<'compute-signal-setup'>}) {
  const {namespace, datasetName} = useParams<{namespace: string; datasetName: string}>();
  if (namespace == null || datasetName == null) {
    throw new Error('Invalid route');
  }
  const [selectedLeafIndex, setSelectedLeafIndex] = React.useState<number | null>(null);
  const signal = page.metadata!.signal;
  const [computeSignal, {isLoading: isComputeSignalLoading, isSuccess: isComputeSignalSuccess}] =
    useComputeSignalColumnMutation();
  const {currentData: webManifest, isFetching: isManifestFetching} = useGetManifestQuery({
    namespace,
    datasetName,
  });
  const schema = webManifest != null ? new Schema(webManifest.dataset_manifest.data_schema) : null;
  if (isManifestFetching || schema == null) {
    return <SlSpinner />;
  }
  const signalLeafs = getLeafsByEnrichmentType(schema.leafs, signal.enrichment_type);
  return (
    <>
      <SlSelect
        className="w-80"
        hoist
        size="small"
        placeholder="Which column to run the signal on?"
        value={(selectedLeafIndex && selectedLeafIndex.toString()) || ''}
        onSlChange={(e) => {
          const index = Number((e.target as HTMLInputElement).value);
          setSelectedLeafIndex(index);
        }}
      >
        {signalLeafs.map(([path], i) => {
          return (
            <SlOption key={i} value={i.toString()}>
              {renderPath(path)}
            </SlOption>
          );
        })}
      </SlSelect>
      <SlButton
        size="small"
        disabled={isComputeSignalLoading}
        className="mt-4"
        onClick={() => {
          const leafPath = selectedLeafIndex != null ? signalLeafs[selectedLeafIndex][0] : null;
          if (leafPath == null) {
            return;
          }
          computeSignal({
            namespace,
            datasetName,
            options: {leaf_path: leafPath, signal: {signal_name: signal.name}},
          });
        }}
      >
        Compute signal
      </SlButton>
      <div className="mt-4 flex items-center">
        <div>
          {isComputeSignalLoading && <SlSpinner />}
          {isComputeSignalSuccess && <SlIcon name="check-lg" />}
        </div>
        {isComputeSignalSuccess && (
          <div className="ml-4 text-sm">
            Check the task list. When the task is complete, refresh the page to see the new signal.
          </div>
        )}
      </div>
    </>
  );
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

  const [
    computeEmbedding,
    {isLoading: isComputeEmbeddingLoading, isSuccess: isComputeEmbeddingSuccess},
  ] = useComputeEmbeddingIndexMutation();
  const [taskId, setTaskId] = React.useState<string | null>(null);

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
              const response = await computeEmbedding({
                namespace,
                datasetName,
                options: {
                  leaf_path: page.metadata!.column!,
                  embedding: {embedding_name: page.metadata?.embedding.name},
                },
              }).unwrap();
              setTaskId(response.task_id);
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
          <div>
            {isComputeEmbeddingSuccess && (
              <>
                <SlSpinner></SlSpinner>
                <br />
                <div className="mt-2 text-gray-500">
                  <p>Loading dataset with task_id "{taskId}".</p>
                  <p>When the task is complete,</p>
                </div>
              </>
            )}
          </div>
        </div>
      </>
    );
  });
}

function Embeddings({onSelect}: {onSelect: (embedding: EmbeddingInfo) => void}) {
  const {namespace, datasetName} = useParams<{namespace: string; datasetName: string}>();
  if (namespace == null || datasetName == null) {
    throw new Error('Invalid route');
  }
  const query = useGetEmbeddingsQuery();
  return renderQuery(query, (embeddings) => {
    return (
      <>
        {embeddings.map((embedding) => {
          const jsonSchema = embedding.json_schema as JSONSchema7;
          return (
            <Item key={embedding.name} onSelect={() => onSelect(embedding)}>
              <div className="flex w-full justify-between">
                <div className="truncate">{embedding.name}</div>
                <div className="truncate">{jsonSchema.description}</div>
              </div>
            </Item>
          );
        })}
      </>
    );
  });
}

function Concepts({onSelect}: {onSelect: (concept: ConceptInfo) => void}) {
  const {namespace, datasetName} = useParams<{namespace: string; datasetName: string}>();
  if (namespace == null || datasetName == null) {
    throw new Error('Invalid route');
  }
  const query = useGetConceptsQuery();
  return renderQuery(query, (concepts) => {
    return (
      <>
        {concepts.map((concept) => {
          return (
            <Item key={concept.name} onSelect={() => onSelect(concept)}>
              <div className="flex w-full justify-between">
                <div className="truncate">
                  {concept.namespace}/{concept.name}
                </div>
                <div className="truncate">{/* Future description here */}</div>
              </div>
            </Item>
          );
        })}
      </>
    );
  });
}

function Columns({
  enrichmentType,
  onSelect,
}: {
  enrichmentType: EnrichmentType;
  onSelect: (path: Path) => void;
}) {
  const {namespace, datasetName} = useParams<{namespace: string; datasetName: string}>();
  if (namespace == null || datasetName == null) {
    throw new Error('Invalid route');
  }

  const query = useGetManifestQuery({
    namespace,
    datasetName,
  });

  const dataSchema = query.currentData?.dataset_manifest.data_schema;
  const schema = dataSchema != null ? new Schema(dataSchema) : null;
  const leafs = schema != null ? getLeafsByEnrichmentType(schema.leafs, enrichmentType) : null;
  const stats = useGetMultipleStatsQuery(
    {namespace, datasetName, leafPaths: leafs?.map(([path]) => path) || []},
    {skip: schema == null}
  );

  return renderQuery(query, () => {
    return (
      <>
        <div
          className="mb-1 flex w-full justify-between
                     border-b-2 border-gray-100 px-4 pb-1 text-sm font-medium"
        >
          <div className="truncate">column</div>
          <div className="flex flex-row items-end justify-items-end text-end">
            <div className="w-24 truncate">count</div>
            <div className="w-24 truncate">avg length</div>
            <div className="w-24 truncate">dtype</div>
          </div>
        </div>
        {leafs!.map(([path, field], i) => {
          const totalCount = stats?.currentData?.[i].total_count;
          const avgTextLength = stats?.currentData?.[i].avg_text_length;
          const avgTextLengthDisplay =
            avgTextLength != null ? Math.round(avgTextLength).toLocaleString() : null;
          return (
            <Item key={i} onSelect={() => onSelect(path)}>
              <div className="flex w-full justify-between">
                <div className="truncate">{renderPath(path)}</div>
                <div className="flex flex-row items-end justify-items-end text-end">
                  <div className="w-24 truncate">
                    {totalCount == null ? <SlSpinner></SlSpinner> : totalCount.toLocaleString()}
                  </div>
                  <div className="w-24 truncate">
                    {avgTextLength == null ? <SlSpinner></SlSpinner> : avgTextLengthDisplay}
                  </div>
                  <div className="w-24 truncate">{field.dtype}</div>
                </div>
              </div>
            </Item>
          );
        })}
      </>
    );
  });
}

function EditConceptAccept({page}: {page: Page<'edit-concept-accept'>}) {
  const {namespace, datasetName} = useParams<{namespace: string; datasetName: string}>();
  if (namespace == null || datasetName == null) {
    throw new Error('Invalid route');
  }

  const [
    computeEmbedding,
    {isLoading: isComputeEmbeddingLoading, isSuccess: isComputeEmbeddingSuccess},
  ] = useComputeEmbeddingIndexMutation();
  const [taskId, setTaskId] = React.useState<string | null>(null);

  return (
    <>
      <SlAlert open variant="warning">
        <SlIcon slot="icon" name="exclamation-triangle" />
        <div className="flex flex-col">
          <div className="flex flex-row text-xs text-gray-500">
            <div className="mr-2">Embedding:</div>
            <div>{page.metadata!.embedding!.name}</div>
          </div>
          <div className="text-xs text-gray-500">
            <div className="flex flex-row text-xs text-gray-500">
              <div className="mr-2">Column:</div>
              <div>{renderPath(page.metadata!.column!)}</div>
            </div>
          </div>
          <div className="mt-2 text-xs">
            <b>This may be expensive!</b>
          </div>
        </div>
      </SlAlert>
      <div className="flex flex-col">
        <SlButton
          onClick={async () => {
            const response = await computeEmbedding({
              namespace,
              datasetName,
              options: {
                leaf_path: page.metadata!.column!,
                embedding: {embedding_name: page.metadata?.embedding.name},
              },
            }).unwrap();
            setTaskId(response.task_id);
          }}
          outline
          variant="success"
          className="mr-4 mt-1 w-16"
        >
          Compute
        </SlButton>
      </div>
      <div>{isComputeEmbeddingLoading && <SlSpinner></SlSpinner>}</div>
      <div>
        {isComputeEmbeddingSuccess && (
          <>
            <SlSpinner></SlSpinner>
            <br />
            <div className="mt-2 text-gray-500">
              <p>Loading dataset with task_id "{taskId}".</p>
              <p>When the task is complete,</p>
            </div>
          </>
        )}
      </div>
    </>
  );
}

function Item({
  children,
  shortcut,
  onSelect = () => {
    return;
  },
  disabled,
}: {
  children: React.ReactNode;
  shortcut?: string;
  onSelect?: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      disabled={disabled}
      style={{color: disabled ? 'var(--sl-color-gray-500)' : ''}}
    >
      {children}
      {shortcut && (
        <div cmdk-shortcuts="">
          {shortcut.split(' ').map((key) => {
            return <kbd key={key}>{key}</kbd>;
          })}
        </div>
      )}
    </Command.Item>
  );
}
