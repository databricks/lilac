import {SerializedError} from '@reduxjs/toolkit';
import {SlSpinner, SlTooltip} from '@shoelace-style/shoelace/dist/react';
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

export function renderError(error: string | SerializedError | undefined): JSX.Element {
  if (error == null) {
    return <></>;
  }
  if (typeof error === 'string') {
    return <>{error}</>;
  }
  // Custom css property exposed by the SlTooltip component.
  const cssProps = {'--max-width': '800px'} as React.CSSProperties;
  return (
    <SlTooltip hoist placement="bottom" style={cssProps}>
      {error.message}
      <span slot="content">
        <pre>{error.stack}</pre>
      </span>
    </SlTooltip>
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
