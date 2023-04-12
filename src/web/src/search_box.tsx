import {SlIcon, SlSpinner} from '@shoelace-style/shoelace/dist/react';
import {Command} from 'cmdk';
import * as React from 'react';
import {Location, useLocation, useNavigate, useParams} from 'react-router-dom';
import {Field} from '../fastapi_client';
import {getEqualBins, NUM_AUTO_BINS} from './db';
import {isOrdinal, LeafValue, Path, Schema, serializePath} from './schema';
import './search_box.css';
import {
  useGetDatasetsQuery,
  useGetManifestQuery,
  useGetStatsQuery,
  useSelectGroupsQuery,
} from './store/api_dataset';
import {renderPath, roundNumber} from './utils';

/** Time to debounce (ms). */
const DEBOUNCE_TIME_MS = 100;
const MAX_FILTER_VALUES_TO_RENDER = 100;

type PageType = 'open-dataset' | 'add-filter' | 'add-filter-value';

type PageMetadata = {
  'open-dataset': Record<string, never>;
  'add-filter': Record<string, never>;
  'add-filter-value': {path: Path; field: Field};
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
            <div key={`${p.type}_${p.name}`} cmdk-badge="" style={{margin: 'auto 2px'}}>
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
  const {isFetching, currentData} = useGetDatasetsQuery();
  const navigate = useNavigate();
  if (isFetching || currentData == null) {
    return <SlSpinner />;
  }
  return (
    <>
      {currentData.map((d) => {
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
  );
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
  const stats = useGetStatsQuery({namespace, datasetName, options: {leaf_path: leafPath}});
  let values: LeafValue[] = [];
  let skipSelectGroups = false;
  let tooManyValues = false;
  if (stats.currentData == null) {
    skipSelectGroups = true;
  } else if (stats.currentData.approx_count_distinct > MAX_FILTER_VALUES_TO_RENDER) {
    skipSelectGroups = true;
    tooManyValues = true;
  }
  if (isOrdinal(field.dtype!) && stats.currentData != null) {
    tooManyValues = false;
    skipSelectGroups = true;
    const bins = getEqualBins(stats.currentData, leafPath, NUM_AUTO_BINS);
    values = [...bins, bins[bins.length - 1]].map((b, i) => {
      const num = roundNumber(b, 2).toLocaleString();
      if (i === 0) {
        return `< ${num}`;
      }
      if (i === bins.length) {
        return `≥ ${num}`;
      }
      const prevNum = roundNumber(bins[i - 1], 2).toLocaleString();
      return `${prevNum} - ${num}`;
    });
  }
  const {isFetching, currentData: groupsResult} = useSelectGroupsQuery(
    {
      namespace,
      datasetName,
      options: {leaf_path: leafPath, limit: 0},
    },
    {skip: skipSelectGroups}
  );

  if (isFetching) {
    return <SlSpinner />;
  }

  if (groupsResult != null) {
    values = groupsResult.map(([value]) => value);
  }

  // Add the current input value to the list of values, and wrap it in quotes.
  if (inputValue.length > 0) {
    values.unshift(`"${inputValue}"`);
  }

  const items = values.map((value, i) => {
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
      {items}
      {tooManyValues && <Item disabled>Too many unique values to list...</Item>}
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
