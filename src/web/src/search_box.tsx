import {SlIcon, SlSpinner} from '@shoelace-style/shoelace/dist/react';
import {Command} from 'cmdk';
import * as React from 'react';
import {Location, useLocation, useNavigate} from 'react-router-dom';
import './search_box.css';
import {useGetDatasetsQuery} from './store/api_dataset';

/** Time to debounce (ms). */
const DEBOUNCE_TIME_MS = 100;

export const SearchBox = () => {
  const ref = React.useRef<HTMLDivElement | null>(null);
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const [inputValue, setInputValue] = React.useState('');
  const [isFocused, setIsFocused] = React.useState(false);
  const location = useLocation();

  const handleFocus = () => setIsFocused(true);
  const handleBlur = (e: React.FocusEvent) => {
    // Ignore blur if the focus is moving to a child of the parent.
    if (e.relatedTarget === ref.current) {
      return;
    }
    setIsFocused(false);
  };
  const [pages, setPages] = React.useState<string[]>([]);
  const activePage = pages[pages.length - 1];
  const isHome = activePage == null;

  const popPage = React.useCallback(() => {
    setPages((pages) => {
      const x = [...pages];
      x.splice(-1, 1);
      return x;
    });
  }, []);

  const pushPage = React.useCallback((page: string) => {
    setPages([...pages, page]);
    inputRef.current?.focus();
  }, []);

  function bounce() {
    if (ref.current == null) {
      return;
    }
    ref.current.style.transform = 'scale(0.96)';
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
        <Command.Input
          ref={inputRef}
          placeholder="Search and run commands"
          onValueChange={(value) => {
            setInputValue(value);
          }}
        />
        <Command.List>
          {isFocused && (
            <>
              <div>
                {pages.map((p) => (
                  <div key={p} cmdk-badge="">
                    {p}
                  </div>
                ))}
              </div>
              <Command.Empty>No results found.</Command.Empty>
              {isHome && <HomeMenu pushPage={pushPage} location={location} />}
              {activePage === 'datasets' && <Datasets />}
            </>
          )}
        </Command.List>
      </Command>
    </div>
  );
};

function HomeMenu({pushPage, location}: {pushPage: (page: string) => void; location: Location}) {
  const datasetSelected = location.pathname.startsWith('/dataset/');
  return (
    <>
      <Command.Group heading="Datasets">
        <Item
          onSelect={() => {
            pushPage('datasets');
          }}
        >
          <SlIcon className="text-xl" name="database" />
          Open dataset
        </Item>
        <Item>
          <SlIcon className="text-xl" name="database-add" />
          Create new dataset
        </Item>
      </Command.Group>
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
      {datasetSelected && (
        <Command.Group heading="Filters">
          <Item>
            <SlIcon className="text-xl" name="database" />
            Add filter
          </Item>
          <Item>
            <SlIcon className="text-xl" name="database" />
            Remove filter
          </Item>
        </Command.Group>
      )}
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

function Datasets() {
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

function Item({
  children,
  shortcut,
  onSelect = () => {
    return;
  },
}: {
  children: React.ReactNode;
  shortcut?: string;
  onSelect?: (value: string) => void;
}) {
  return (
    <Command.Item onSelect={onSelect}>
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
