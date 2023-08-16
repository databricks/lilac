import {defaultDatasetViewState, type DatasetViewState} from './stores/datasetViewStore';
import {serializeState} from './stores/urlHashStore';

export function notEmpty<TValue>(value: TValue | null | undefined): value is TValue {
  return value !== null && value !== undefined;
}

export function conceptIdentifier(namespace: string, conceptName: string) {
  return `${namespace}/${conceptName}`;
}

export function conceptLink(namespace: string, conceptName: string) {
  return `/concepts#${conceptIdentifier(namespace, conceptName)}`;
}

export function datasetIdentifier(namespace: string, datasetName: string) {
  return `${namespace}/${datasetName}`;
}

export function datasetLink(
  namespace: string,
  datasetName: string,
  datasetViewState?: DatasetViewState
): string {
  let hashState: string | null = null;
  if (datasetViewState != null) {
    const defaultState = defaultDatasetViewState(namespace, datasetName);
    hashState = serializeState(datasetViewState, defaultState);
  }
  return `/datasets#${datasetIdentifier(namespace, datasetName)}${
    hashState != null ? `&${hashState}` : ''
  }`;
}

export function signalLink(name: string) {
  return `/signals#${name}`;
}
