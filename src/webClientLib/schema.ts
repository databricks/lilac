import { DataType, EnrichmentType, Field, Schema, Schema as SchemaJSON } from './fastapi_client';

export type LilacDataType = Exclude<DataType, 'list'> | `${Exclude<DataType, 'list'>}[]`;

export type LeafValue<T extends LilacDataType = LilacDataType> =
  | (T extends 'string'
      ? string
      : T extends 'boolean'
      ? boolean
      : T extends DataTypeNumber
      ? number
      : T extends 'string_span'
      ? { start: number; end: number }
      : T extends 'time' | 'date' | 'timestamp' | 'interval' | 'binary'
      ? Date
      : T extends 'struct'
      ? LeafStruct
      : T extends 'list'
      ? LeafList
      : T extends `${infer U extends Exclude<DataType, 'list'>}[]`
      ? LeafValue<U>[]
      : never)
  | null;

type LeafStruct = object;
type LeafList = LeafValue[];
export type FieldValue = FieldValue[] | { [fieldName: string]: FieldValue } | LeafValue;

export interface Item {
  [column: string]: FieldValue;
}

export interface ImageInfo {
  path: Path;
}

export type Path = Array<string>;

export const PATH_WILDCARD = '*';
export const UUID_COLUMN = '__rowid__';
export const LILAC_COLUMN = '__lilac__';

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

export function isFloat(dtype: DataType) {
  return ['float16', 'float32', 'float64'].indexOf(dtype) >= 0;
}

export function isInteger(dtype: DataType) {
  return (
    ['int8', 'int16', 'int32', 'int64', 'uint8', 'uint16', 'uint32', 'uint64'].indexOf(dtype) >= 0
  );
}

export function isTemporal(dtype: DataType) {
  return ['time', 'date', 'timestamp', 'interval'].indexOf(dtype) >= 0;
}

export function isOrdinal(dtype: DataType) {
  return isFloat(dtype) || isInteger(dtype) || isTemporal(dtype);
}

export function serializePath(path: Path): string {
  return path.map((p) => `${p}`).join('.');
}

/**
 * Returns a dictionary that maps a "leaf path" to all flatten values for that leaf.
 */
export function getLeafVals(item: Item): { [pathStr: string]: LeafValue[] } {
  const q: [Path, FieldValue][] = [];
  q.push([[], item]);
  const result: { [pathStr: string]: LeafValue[] } = {};
  while (q.length > 0) {
    const [path, value] = q.pop()!;
    if (Array.isArray(value)) {
      for (const v of value) {
        const childPath = [...path, PATH_WILDCARD];
        q.push([childPath, v]);
      }
    } else if (value != null && typeof value === 'object') {
      for (const [fieldName, childField] of Object.entries(value)) {
        const childPath = [...path, fieldName];
        q.push([childPath, childField]);
      }
    } else {
      const pathStr = serializePath(path);
      if (!(pathStr in result)) {
        result[pathStr] = [];
      }
      result[pathStr].push(value);
    }
  }
  return result;
}

export function getLeafsByEnrichmentType(leafs: [Path, Field][], enrichmentType?: EnrichmentType) {
  if (enrichmentType == null) {
    return leafs;
  }
  if (enrichmentType !== 'text') {
    throw new Error(`Unsupported enrichment type: ${enrichmentType}`);
  }
  return leafs.filter(([path, field]) => leafMatchesEnrichmentType([path, field], enrichmentType));
}

export function leafMatchesEnrichmentType(
  [, field]: [Path, Field],
  enrichmentType: EnrichmentType
): boolean {
  if (enrichmentType === 'text' && ['string', 'string_span'].includes(field.dtype!)) {
    return true;
  }
  return false;
}

export class LilacSchema {
  readonly fields: { [fieldName: string]: Field };
  readonly leafs: [Path, Field][] = [];

  /** Maps a field path in the schema to a primitive field (leaf). */
  private readonly leafByPath: { [path: string]: Field } = {};

  constructor(schemaJSON: SchemaJSON) {
    this.fields = schemaJSON.fields;
    this.populateLeafs();
  }

  private populateLeafs() {
    const q: [Path, Field][] = [];
    q.push([[], this as unknown as Field]);
    while (q.length > 0) {
      const [path, field] = q.pop()!;
      if (field.fields != null) {
        for (const [fieldName, childField] of Object.entries(field.fields)) {
          const childPath = [...path, fieldName];
          q.push([childPath, childField]);
        }
      } else if (field.repeated_field != null) {
        const childPath = [...path, PATH_WILDCARD];
        q.push([childPath, field.repeated_field]);
      } else {
        this.leafByPath[serializePath(path)] = field;
        this.leafs.push([path, field]);
      }
    }
  }

  getLeaf(leafPath: Path): Field {
    let field: Field = { fields: this.fields };
    for (const path of leafPath) {
      if (field.repeated_field && path === PATH_WILDCARD) {
        field = field.repeated_field;
      } else {
        if (!field.fields?.[path]) {
          throw new Error(`Leaf with path ${JSON.stringify(leafPath)} was not found.`);
        }
        field = field.fields[path];
      }
    }
    return field;
  }
}

export function getFieldByPath(schema: Schema, path: Path): Field | undefined {
  let field: Field = { fields: schema.fields };
  for (const p of path) {
    if (field.repeated_field && p === PATH_WILDCARD) {
      field = field.repeated_field;
    } else {
      if (!field.fields?.[p]) {
        return;
      }
      field = field.fields[p];
    }
  }
  return field;
}

export function getValueByPath(values: any, path: Path): FieldValue {
  let value: FieldValue = values;
  let prevP: string | undefined;
  for (const p of path) {
    if (value == null) {
      return null;
    }
    if (p === PATH_WILDCARD) {
      prevP = p;
      continue;
    } else if (prevP === PATH_WILDCARD) {
      if (!Array.isArray(value)) {
        return null;
      }
      value = value.map((v: any) => v[p]);
    } else if (typeof value === 'object') {
      value = value[p];
    }

    prevP = p;
  }
  return value;
}
