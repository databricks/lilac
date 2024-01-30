import {base} from '$app/paths';
import {defaultDatasetViewState, type DatasetViewState} from './stores/datasetViewStore';
import type {NavigationState} from './stores/navigationStore';
import {getStateHash, serializeState} from './stores/urlHashStore';

export function notEmpty<TValue>(value: TValue | null | undefined): value is TValue {
  return value !== null && value !== undefined;
}

export function conceptIdentifier(namespace: string, conceptName: string) {
  return `${namespace}/${conceptName}`;
}

export function conceptLink(namespace: string, conceptName: string) {
  return `${base}/concepts#${conceptIdentifier(namespace, conceptName)}`;
}

export function datasetIdentifier(namespace: string, datasetName: string) {
  return `${namespace}/${datasetName}`;
}

export function datasetLink(
  namespace: string,
  datasetName: string,
  navState: NavigationState,
  datasetViewState?: DatasetViewState
): string {
  let hashState: string | null = null;
  if (datasetViewState != null) {
    const defaultState = defaultDatasetViewState(namespace, datasetName);
    hashState = serializeState(datasetViewState, defaultState);
  }
  const hash = getStateHash(datasetIdentifier(namespace, datasetName), navState, hashState);
  return `${base}/datasets${hash}`;
}

export function signalLink(name: string) {
  return `${base}/signals#${name}`;
}

export function newDatasetLink() {
  return `${base}/datasets/new`;
}

export function homeLink() {
  return `${base}/`;
}

export function ragLink() {
  return `${base}/rag`;
}

export function settingsLink() {
  return `${base}/settings`;
}

export function datasetLoadingLink(namespace: string, datasetName: string, taskId: string) {
  return `${base}/datasets/loading#${datasetIdentifier(namespace, datasetName)}/${taskId}`;
}
