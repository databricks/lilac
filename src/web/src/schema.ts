import {DataType, Field, Schema as SchemaJSON} from '../fastapi_client';
export type LeafValue = number | boolean | string | null;
export type FieldValue = FieldValue[] | {[fieldName: string]: FieldValue} | LeafValue;

export interface Item {
  [column: string]: FieldValue;
}

export interface ImageInfo {
  path: Path;
}

export type Path = Array<string | number>;

export const PATH_WILDCARD = '*';
export const UUID_COLUMN = '__rowid__';

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
  return path.map((p) => `"${p}"`).join('.');
}

/**
 * Returns a dictionary that maps a "leaf path" to all flatten values for that leaf.
 */
export function getLeafVals(item: Item): {[pathStr: string]: LeafValue[]} {
  const q: [Path, FieldValue][] = [];
  q.push([[], item]);
  const result: {[pathStr: string]: LeafValue[]} = {};
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

export class Schema {
  readonly fields: {[fieldName: string]: Field};
  readonly leafs: [Path, Field][] = [];

  /** Maps a field path in the schema to a primitive field (leaf). */
  private readonly leafByPath: {[path: string]: Field} = {};

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
    const serializedPath = serializePath(leafPath);
    const leaf = this.leafByPath[serializedPath];
    if (leaf == null) {
      throw new Error(`Leaf with path ${JSON.stringify(leafPath)} was not found.`);
    }
    return leaf;
  }
}
