import {SerializedError} from '@reduxjs/toolkit';
import {SlAlert, SlIcon, SlSpinner} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {ConceptInfo, EmbeddingInfo} from '../fastapi_client';
import {Path} from './schema';

export function renderQuery<T>(
  queryResult: {
    isFetching?: boolean;
    error?: string | SerializedError | undefined | unknown;
    currentData?: T;
    data?: T;
  },
  render: (data: T) => JSX.Element
): JSX.Element {
  if (queryResult == null) {
    return <></>;
  }
  const {isFetching, error, currentData} = queryResult;

  if (error) {
    return <div>Failed to render. See the toast notification for error details.</div>;
  }

  if (currentData != null) {
    return render(currentData);
  }

  if (isFetching) {
    return <SlSpinner />;
  }

  return <></>;
}

const Error = ({error}: {error: SerializedError}): JSX.Element => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const primary = React.useRef<any>();

  React.useEffect(() => {
    primary.current.toast();
  });

  return (
    <SlAlert ref={primary} style={{width: 'auto'}} variant="danger" closable>
      <SlIcon slot="icon" name="info-circle" />
      <strong>{error.name}</strong>
      <br />
      <pre>{error.message}</pre>
    </SlAlert>
  );
};

export function renderError(error: unknown): JSX.Element {
  if (error == null) {
    return <></>;
  }
  if (typeof error === 'string') {
    return (
      <p className="text-red-500">
        <pre>{error}</pre>
      </p>
    );
  }

  return (
    <div>
      <Error error={error as SerializedError}></Error>
    </div>
  );
}

export function renderPath(leafPath: Path): string {
  return leafPath.join('.');
}

export function getConceptAlias(
  concept: ConceptInfo,
  column: Path,
  embedding: EmbeddingInfo
): string {
  return `${concept.namespace}/${concept.name}` + `(${renderPath(column)}, ${embedding.name})`;
}

export function getDatasetLink(namespace: string, datasetName: string): string {
  return `/datasets/${namespace}/${datasetName}`;
}

export function roundNumber(val: number, precision: number): number {
  return Number(val.toFixed(precision));
}

export function formatDatetime(date: Date) {
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);

  const isToday = today.toDateString() == date.toDateString();
  const isYesterday = yesterday.toDateString() == date.toDateString();
  if (isToday || isYesterday) {
    return `${isToday ? 'Today' : 'Yesterday'} ${date.toLocaleString([], {
      hour: '2-digit',
      minute: '2-digit',
    })}`;
  }
  return date.toLocaleString([], {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
/**
 * Hook that calls the callback when a click happens outside of the ref.
 * @param ref The ref to check for clicks outside of.
 * @param ignoreRefs The refs to ignore clicks on.
 * @param callback The callback to call when a click happens outside of the ref.
 */
export function useClickOutside(
  ref: React.RefObject<HTMLElement>,
  ignoreRefs: React.RefObject<HTMLElement>[],
  callback: () => unknown
) {
  React.useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      // Get a bit for when the click is on any of the ignoreRefs.
      const ignoreClick = ignoreRefs.some((ignoreRef) => {
        if (ignoreRef.current == null) {
          return false;
        }
        return ignoreRef.current.contains(event.target as Node);
      });

      if (ref.current && !ref.current.contains(event.target as Node) && !ignoreClick) {
        callback();
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [ref]);
}
