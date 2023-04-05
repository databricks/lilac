import {SerializedError} from '@reduxjs/toolkit';
import {SlTooltip} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {Path} from './schema';

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

export function getModelLink(username: string, modelName: string): string {
  return `/${username}/${modelName}`;
}

export function roundNumber(val: number, precision: number): number {
  return Number(val.toFixed(precision));
}

export function formatDatetime(datetime: string): string {
  const date = new Date(datetime);
  return date.toLocaleDateString('en-US', {year: 'numeric', month: 'long', day: 'numeric'});
}
