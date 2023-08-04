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

export function datasetLink(namespace: string, datasetName: string) {
  return `/datasets#${datasetIdentifier(namespace, datasetName)}`;
}
