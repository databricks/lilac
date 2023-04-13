import {SlIcon, SlSpinner} from '@shoelace-style/shoelace/dist/react';
import {Command} from 'cmdk';
import {JSONSchema7} from 'json-schema';
import * as React from 'react';
import {Location, useLocation, useNavigate, useParams} from 'react-router-dom';
import {Field} from '../fastapi_client';
import {Path, Schema, serializePath} from './schema';
import './search_box.css';
import {useGetDatasetsQuery, useGetManifestQuery, useGetSignalsQuery} from './store/api_dataset';
import {useTopValues} from './store/store';
import {renderPath, renderQuery} from './utils';

/** Time to debounce (ms). */
const DEBOUNCE_TIME_MS = 100;

type PageType = 'open-dataset' | 'add-filter' | 'add-filter-value' | 'run-signal';

type PageMetadata = {
  'open-dataset': Record<string, never>;
  'add-filter': Record<string, never>;
  'add-filter-value': {path: Path; field: Field};
  'run-signal': Record<string, never>;
};

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

  const handleFocus = () => setIsFocused(true);
  const handleBlur = (e: React.FocusEvent) => {
    // Ignore blur if the focus is moving to a child of the parent.
    if (e.relatedTarget === ref.current) {
      return;
    }
    setIsFocused(false);
  };

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
        onBlur={handleBlur}
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
        <div className="flex">
          {pages.map((p) => (
            <div key={`${p.type}_${p.name}`} cmdk-badge="" className="truncate">
              {p.name}
            </div>
          ))}
          <Command.Input
            value={inputValue}
            ref={inputRef}
            style={{width: 'auto', flexGrow: 1}}
            placeholder="Search and run commands"
            onValueChange={setInputValue}
          />
        </div>
        <Command.List>
          {isFocused && (
            <>
              <div className="mt-4"></div>
              <Command.Empty>No results found.</Command.Empty>
              {isHome && <HomeMenu pushPage={pushPage} location={location} closeMenu={closeMenu} />}
              {activePage?.type === 'open-dataset' && <Datasets closeMenu={closeMenu} />}
              {activePage?.type == 'add-filter' && <AddFilter pushPage={pushPage} />}
              {activePage?.type == 'add-filter-value' && (
                <AddFilterValue
                  inputValue={inputValue}
                  closeMenu={closeMenu}
                  page={activePage as Page<'add-filter-value'>}
                />
              )}
              {activePage?.type == 'run-signal' && <RunSignal closeMenu={closeMenu} />}
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
              pushPage({type: 'run-signal', name: 'Run signal'});
            }}
          >
            <SlIcon className="text-xl" name="stars" />
            Run signal
          </Item>
        </Command.Group>
      )}

      {/* Concepts */}
      <Command.Group heading="Concepts">
        <Item>
          <SlIcon className="text-xl" name="stars" />
          Open concept
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

function RunSignal({closeMenu}: {closeMenu: () => void}) {
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
                closeMenu();
                // TODO(smilkov): Run the signal.
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
