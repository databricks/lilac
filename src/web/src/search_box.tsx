import {SlIcon, SlSpinner} from '@shoelace-style/shoelace/dist/react';
import {Command} from 'cmdk';
import * as React from 'react';
import './search_box.css';
import {useGetDatasetsQuery} from './store/api_dataset';

export const SearchBox = () => {
  const ref = React.useRef<HTMLDivElement | null>(null);
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const [inputValue, setInputValue] = React.useState('');
  // const [open, setOpen] = React.useState(false);
  const [isFocused, setIsFocused] = React.useState(false);

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
    }, 100);

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
          placeholder="Search and run commands..."
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
              {isHome && <HomeMenu pushPage={pushPage} />}
              {activePage === 'datasets' && <Datasets />}
            </>
          )}
        </Command.List>
      </Command>
    </div>
  );
};

function HomeMenu({pushPage}: {pushPage: (page: string) => void}) {
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
      <Command.Group heading="Help">
        <Item>
          <DocsIcon />
          Search Docs...
        </Item>
        <Item>
          <FeedbackIcon />
          Create a GitHub issue
        </Item>
        <Item>
          <ContactIcon />
          Contact us
        </Item>
      </Command.Group>
    </>
  );
}

function Datasets() {
  const {isFetching, currentData} = useGetDatasetsQuery();
  if (isFetching || currentData == null) {
    return <SlSpinner />;
  }
  return (
    <>
      {currentData.map((d) => {
        const key = `${d.namespace}/${d.dataset_name}`;
        return (
          <Item key={key}>
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

function DocsIcon() {
  return (
    <svg
      fill="none"
      height="24"
      shapeRendering="geometricPrecision"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.5"
      viewBox="0 0 24 24"
      width="24"
    >
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"></path>
      <path d="M14 2v6h6"></path>
      <path d="M16 13H8"></path>
      <path d="M16 17H8"></path>
      <path d="M10 9H8"></path>
    </svg>
  );
}

function FeedbackIcon() {
  return (
    <svg
      fill="none"
      height="24"
      shapeRendering="geometricPrecision"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.5"
      viewBox="0 0 24 24"
      width="24"
    >
      {/* eslint-disable-next-line max-len */}
      <path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z"></path>
    </svg>
  );
}

function ContactIcon() {
  return (
    <svg
      fill="none"
      height="24"
      shapeRendering="geometricPrecision"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.5"
      viewBox="0 0 24 24"
      width="24"
    >
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
      <path d="M22 6l-10 7L2 6"></path>
    </svg>
  );
}
