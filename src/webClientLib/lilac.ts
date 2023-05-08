import type { DataType, Field, Schema } from './fastapi_client';
import {
  ENTITY_FEATURE_KEY,
  LILAC_COLUMN,
  PATH_WILDCARD,
  pathIsEqual,
  type DataTypeCasted,
  type FieldValue,
  type Path
} from './schema';
import { mergeDeep } from './utils';

const VALUE_KEY = '__value';
const PATH_KEY = '__path';
const SCHEMA_FIELD_KEY = '__field';

// Cache containing the list of fields and value nodes
let listFieldsCache = new WeakMap<LilacSchemaField, LilacSchemaField[]>();
let listValueNodesCache = new WeakMap<LilacValueNode, LilacValueNode[]>();

export type LilacSchemaField = Field & {
  path: Path;
  // Overwrite the fields and repeated_field properties to be LilacSchemaField
  repeated_field?: LilacSchemaField;
  fields?: Record<string, LilacSchemaField>;
};
export type LilacSchema = LilacSchemaField;

export type LilacValueNode = {
  readonly [key: string | number]: LilacValueNode;
};

/**
 * Internal type for a LilacValueNode casted with internal properties.
 */
type LilacValueNodeCasted<D extends DataType = DataType> = {
  /** Holds the actual value of the node */
  [VALUE_KEY]: DataTypeCasted<D>;
  /** Holds the path property of the node */
  [PATH_KEY]: Path;
  /** Holds a reference to the schema field */
  [SCHEMA_FIELD_KEY]: LilacSchemaField | undefined;
};

/**
 * Cast a value node to an internal value node
 */
function castLilacValueNode<D extends DataType = DataType>(
  node: LilacValueNode
): LilacValueNodeCasted<D> {
  return node as unknown as LilacValueNodeCasted;
}

/**
 * Deserialize a raw schema response to a LilacSchema.
 */
export function deserializeSchema(rawSchema: Schema): LilacSchema {
  const lilacFields = lilacSchemaFieldFromField(rawSchema, []);

  if (!lilacFields.fields) {
    return { fields: {}, path: [] };
  }

  const { [LILAC_COLUMN]: signalsFields, ...rest } = lilacFields.fields;
  let fields = rest;

  // Merge the signal fields into the source fields
  if (signalsFields?.fields) {
    fields = mergeDeep(fields, signalsFields.fields);
  }

  // Convert the fields to LilacSchemaField
  return { fields, path: [] };
}

export function deserializeRow(rawRow: FieldValue, schema: LilacSchema): LilacValueNode {
  const fields = listFields(schema);
  const children = lilacValueNodeFromRawValue(rawRow, fields, []);

  if (Array.isArray(children)) {
    throw new Error('Expected row to have a single root node');
  }
  if (!children) {
    throw new Error('Expected row to have children');
  }

  const { [LILAC_COLUMN]: signalValues, ...values } = children;

  // Merge signal values into the source values
  let mergedNode: LilacValueNode = values;
  if (signalValues) mergedNode = mergeDeep(values, signalValues);

  castLilacValueNode(mergedNode)[VALUE_KEY] = null;
  castLilacValueNode(mergedNode)[PATH_KEY] = [];
  castLilacValueNode(mergedNode)[SCHEMA_FIELD_KEY] = schema;
  return mergedNode;
}

/** List all fields as a flattend array */
export function listFields(field: LilacSchemaField | LilacSchema | undefined): LilacSchemaField[] {
  if (!field) return [];
  // Return the cached value if it exists
  // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
  if (listFieldsCache.has(field)) return listFieldsCache.get(field)!;

  const result = [
    field,
    ...Object.values(field.fields || {}).flatMap(listFields),
    ...(field.repeated_field ? listFields(field.repeated_field) : [])
  ].filter((f) => f.path.length > 0);

  // Cache the result
  listFieldsCache.set(field, result);
  return result;
}

/** List all values as a flattend array */
export function listValueNodes(row: LilacValueNode): LilacValueNode[] {
  // Return the cached value if it exists
  // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
  if (listValueNodesCache.has(row)) return listValueNodesCache.get(row)!;

  let result: LilacValueNode[];
  if (Array.isArray(row)) result = [...row, ...row.flatMap(listValueNodes)];
  else {
    // Strip the internal properties
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { [VALUE_KEY]: value, [PATH_KEY]: path, [SCHEMA_FIELD_KEY]: field, ...rest } = row;

    const childProperties = Object.values(rest || {});
    result = [...childProperties, ...childProperties.flatMap((v) => listValueNodes(v))];
  }

  // Cache the result
  listValueNodesCache.set(row, result);
  return result;
}

/**
 * Get a field in schema by path
 */
export function getField(schema: LilacSchema, path: Path): LilacSchemaField | undefined {
  const list = listFields(schema);
  return list.find((field) => pathIsEqual(field.path, path));
}

/**
 * Get the first value at the given path in a row
 */
export function getValueNode(row: LilacValueNode, _path: Path): LilacValueNode | undefined {
  const list = listValueNodes(row);
  return list.find((value) => pathIsEqual(L.path(value), _path));
}

/**
 * Get all values at the given path in a row
 */
export function getValueNodes(row: LilacValueNode, _path: Path): LilacValueNode[] {
  const list = listValueNodes(row);
  return list.filter((value) => pathIsEqual(L.path(value), _path));
}

/**
 * Determine if field is produced by a signal
 */
export function isSignalField(field: LilacSchemaField): boolean {
  return field.path[0] === LILAC_COLUMN;
}

export const L = {
  path: (value: LilacValueNode): Path | undefined => {
    if (!value) return undefined;
    return castLilacValueNode(value)[PATH_KEY];
  },
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  value: <D extends DataType>(value: LilacValueNode, dtype?: D): DataTypeCasted<D> | undefined => {
    if (!value) return undefined;
    return castLilacValueNode(value)[VALUE_KEY] as DataTypeCasted<D>;
  },
  field: (value: LilacValueNode): LilacSchemaField | undefined => {
    if (!value) return undefined;
    return castLilacValueNode(value)[SCHEMA_FIELD_KEY];
  },
  dtype: (value: LilacValueNode): DataType | undefined => {
    const _field = L.field(value);
    return _field?.dtype;
  }
};

/**
 * Convert raw schema field to LilacSchemaField.
 * Adds path attribute to each field
 */
function lilacSchemaFieldFromField(field: Field, path: Path): LilacSchemaField {
  const { fields, repeated_field, ...rest } = field;
  const lilacField: LilacSchemaField = { ...rest, path: [] };
  if (fields) {
    lilacField.fields = {};
    for (const [fieldName, field] of Object.entries(fields)) {
      const lilacChildField = lilacSchemaFieldFromField(field, [...path, fieldName]);
      lilacChildField.path = [...path, fieldName];
      lilacField.fields[fieldName] = lilacChildField;
    }
  }
  if (repeated_field) {
    const lilacChildField = lilacSchemaFieldFromField(repeated_field, [...path, PATH_WILDCARD]);
    lilacChildField.path = [...path, PATH_WILDCARD];
    lilacField.repeated_field = lilacChildField;
  }
  // Copy dtype from the child field (issue/125)
  if (lilacField.is_entity && lilacField.fields?.[ENTITY_FEATURE_KEY]?.dtype) {
    lilacField.dtype = lilacField.fields?.[ENTITY_FEATURE_KEY]?.dtype;
  }
  return lilacField;
}

function lilacValueNodeFromRawValue(
  rawFieldValue: FieldValue,
  fields: LilacSchemaField[],
  path: Path
): LilacValueNode {
  const field = fields.find((field) => pathIsEqual(field.path, path));

  let ret: LilacValueNode = {};
  if (Array.isArray(rawFieldValue)) {
    ret = rawFieldValue.map((value) =>
      lilacValueNodeFromRawValue(value, fields, [...path, PATH_WILDCARD])
    ) as Record<number, LilacValueNode>;
    castLilacValueNode(ret)[VALUE_KEY] = null;
    return ret;
  } else if (rawFieldValue && typeof rawFieldValue === 'object') {
    const { [ENTITY_FEATURE_KEY]: entityValue, ...rest } = rawFieldValue;

    ret = Object.entries(rest).reduce<Record<string, LilacValueNode>>((acc, [key, value]) => {
      acc[key] = lilacValueNodeFromRawValue(value, fields, [...path, key]);
      return acc;
    }, {});
    castLilacValueNode(ret)[VALUE_KEY] = entityValue || null;
  } else {
    castLilacValueNode(ret)[VALUE_KEY] = rawFieldValue;
  }
  castLilacValueNode(ret)[PATH_KEY] = path;
  castLilacValueNode(ret)[SCHEMA_FIELD_KEY] = field;
  return ret;
}

export function clearCache() {
  listFieldsCache = new WeakMap();
  listValueNodesCache = new WeakMap();
}
