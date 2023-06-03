export function notEmpty<TValue>(value: TValue | null | undefined): value is TValue {
  return value !== null && value !== undefined;
}

export function conceptLink(namespace: string, conceptName: string) {
  return `/concepts#!/${namespace}/${conceptName}`;
}

export function datasetLink(namespace: string, datasetName: string) {
  return `/datasets#!/${namespace}/${datasetName}`;
}
