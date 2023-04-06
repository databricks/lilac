import {SerializedError} from '@reduxjs/toolkit';
import {SlAlert, SlIcon, SlSpinner} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {Path} from './schema';

export function renderQuery<T>(
  queryResult: {
    isFetching?: boolean;
    error?: string | SerializedError | undefined;
    currentData?: T;
  },
  render: (data: T) => JSX.Element
): JSX.Element {
  if (queryResult == null) {
    return <></>;
  }
  const {isFetching, error, currentData} = queryResult;
  if (isFetching) {
    return <SlSpinner />;
  }
  if (error || currentData == null) {
    return renderError(error);
  }
  return render(queryResult.currentData!);
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

export function renderError(error: string | SerializedError | undefined): JSX.Element {
  if (error == null) {
    return <></>;
  }
  if (typeof error === 'string') {
    return <>{error}</>;
  }

  return (
    <div>
      <Error error={error}></Error>
    </div>
  );
}

export function renderPath(leafPath: Path): string {
  return leafPath.join('.');
}

export function getDatasetLink(namespace: string, datasetName: string): string {
  return `/datasets/${namespace}/${datasetName}`;
}

export function roundNumber(val: number, precision: number): number {
  return Number(val.toFixed(precision));
}

export function formatDatetime(datetime: string): string {
  const date = new Date(datetime);
  return date.toLocaleDateString('en-US', {year: 'numeric', month: 'long', day: 'numeric'});
}
