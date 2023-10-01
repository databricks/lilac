import type {Column, ConceptSignal, DataType, Signal, SignalInputType} from '../fastapi_client';
import type {LilacField} from './lilac';
export type LeafValue = number | boolean | string | null;
export type FieldValue = FieldValue[] | {[fieldName: string]: FieldValue} | LeafValue;

export interface Item {
  [column: string]: FieldValue;
}

export interface ImageInfo {
  path: Path;
}

export type Path = Array<string>;

export const PATH_WILDCARD = '*';
export const ROWID = '__rowid__';
export const VALUE_KEY = '__value__';
export const SPAN_KEY = '__span__';

export const SIGNAL_INPUT_TYPE_TO_VALID_DTYPES: Record<SignalInputType, DataType[]> = {
  text: ['string', 'string_span'],
  text_embedding: ['embedding'],
  image: ['binary']
};

export type DataTypeNumber =
  | 'int8'
  | 'int16'
  | 'int32'
  | 'int64'
  | 'uint8'
  | 'uint16'
  | 'uint32'
  | 'uint64'
  | 'float16'
  | 'float32'
  | 'float64';

export type DataTypeCasted<D extends DataType = DataType> =
  | (D extends 'string'
      ? string
      : D extends 'boolean'
      ? boolean
      : D extends DataTypeNumber
      ? number
      : D extends 'string_span'
      ? {start: number; end: number}
      : D extends 'time' | 'date' | 'timestamp' | 'interval' | 'binary'
      ? string
      : D extends 'struct'
      ? object
      : D extends 'list'
      ? unknown[]
      : never)
  | null;

export function isNumeric(dtype: DataType) {
  return isFloat(dtype) || isInteger(dtype);
}
export function isFloat(dtype: DataType | undefined): dtype is 'float16' | 'float32' | 'float64' {
  return ['float16', 'float32', 'float64'].indexOf(dtype ?? '') >= 0;
}

export function isInteger(
  dtype: DataType
): dtype is 'int8' | 'int16' | 'int32' | 'int64' | 'uint8' | 'uint16' | 'uint32' | 'uint64' {
  return (
    ['int8', 'int16', 'int32', 'int64', 'uint8', 'uint16', 'uint32', 'uint64'].indexOf(dtype) >= 0
  );
}

export function isTemporal(dtype: DataType) {
  return ['time', 'date', 'timestamp', 'interval'].indexOf(dtype) >= 0;
}

export function isOrdinal(dtype: DataType) {
  return isFloat(dtype) || isInteger(dtype) || isTemporal(dtype) || dtype === 'boolean';
}

export function serializePath(path: Path | string): string {
  if (typeof path === 'string') return path;

  return path.map(p => (p.includes('.') ? `"${p}"` : p)).join('.');
}

export function isSortableField(field: LilacField) {
  if (field.repeated_field) {
    return isSortableField(field.repeated_field);
  }
  return field.dtype && !(['embedding', 'binary'] as DataType[]).includes(field.dtype);
}

export function isFilterableField(field: LilacField) {
  return field.dtype && !(['embedding', 'binary'] as DataType[]).includes(field.dtype);
}

export function deserializePath(path: string | Path): Path {
  if (Array.isArray(path)) return path;
  // Regex taken from:
  // https://stackoverflow.com/questions/70059085/javascript-regular-expression-split-string-by-periods-not-in-double-quotes
  const matches = path.match(/(?:"[^"]*"|[^.])+(?:\.+$)?/g)?.map(match => match.replace(/"/g, ''));
  return matches || [];
}
export function pathIsEqual(
  path1: Path | string | undefined,
  path2: Path | string | undefined
): boolean {
  if (!path1 || !path2) return false;
  path1 = deserializePath(path1);
  path2 = deserializePath(path2);
  if (path1.length !== path2.length) return false;
  for (let i = 0; i < path1.length; i++) {
    if (path1[i] === PATH_WILDCARD && path2[i].match(/\d/g)) continue;
    if (path1[i].match(/\d/g) && path2[i] === PATH_WILDCARD) continue;
    if (path1[i] !== path2[i]) return false;
  }
  return true;
}

export function pathIncludes(
  path: Path | string | undefined,
  prefix: Path | string | undefined
): boolean {
  if (!path || !prefix) return false;
  path = deserializePath(path);
  prefix = deserializePath(prefix);
  if (path.length < prefix.length) return false;
  return pathIsEqual(path.slice(0, prefix.length), prefix);
}

/**
 * Returns true if path2 matches the pattern of path1
 * @param path1 Path that may contain wildcard pattern
 * @param path2 Path to match against path1
 */
export function pathIsMatching(path1: Path | string | undefined, path2: Path | string | undefined) {
  if (!path1 || !path2) return false;
  path1 = deserializePath(path1);
  path2 = deserializePath(path2);
  if (path1.length !== path2.length) return false;
  for (let i = 0; i < path1.length; i++) {
    if (path1[i] === path2[i]) continue;
    if (path1[i] !== path2[i] && path1[i] !== PATH_WILDCARD) return false;
    if (path1[i] === PATH_WILDCARD) {
      if (!path2[i].toString().match(/^\d+$/)) return false;
    }
  }
  return true;
}
export function isConceptSignal(
  signal: ConceptSignal | Signal | undefined
): signal is ConceptSignal {
  return signal?.signal_name === 'concept_score';
}

export function formatValue(value: DataTypeCasted | string[] | Blob, numDigits = 3) {
  if (value == null) {
    return 'N/A';
  }
  if (typeof value === 'number') {
    return value.toLocaleString(undefined, {maximumFractionDigits: numDigits});
  }
  if (value instanceof Blob) {
    return 'blob';
  }
  if (Array.isArray(value)) {
    return value.join(', ');
  }
  if (typeof value === 'object') {
    if (Object.keys(value).length === 2 && value.start != null && value.end != null) {
      return `(${value.start}, ${value.end})`;
    }
    return JSON.stringify(value);
  }
  return value.toString();
}

export function isColumn(pathOrColumn: string | string[] | Column): pathOrColumn is Column {
  return (pathOrColumn as Column).path != undefined;
}
