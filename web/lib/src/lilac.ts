import type {JSONSchema7} from 'json-schema';
import type {DataType, Field, Schema, Signal, SignalInfo} from '../fastapi_client';
import {
  PATH_WILDCARD,
  VALUE_KEY,
  pathIncludes,
  pathIsMatching,
  type DataTypeCasted,
  type FieldValue,
  type LeafValue,
  type Path
} from './schema';

const PATH_KEY = '__path__';
const SCHEMA_FIELD_KEY = '__field__';

// Cache containing the list of fields and value nodes
let listFieldsCache = new WeakMap<LilacSchemaField, LilacSchemaField[]>();
let listValueNodesCache = new WeakMap<LilacValueNode, LilacValueNode[]>();

export type LilacSchemaField<S extends Signal = Signal> = Field & {
  path: Path;
  alias?: Path;
  // Overwrite the fields and repeated_field properties to be LilacSchemaField
  repeated_field?: LilacSchemaField;
  fields?: Record<string, LilacSchemaField>;
  // Overwrite signal type from generic
  signal?: S;
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
export function deserializeSchema(
  rawSchema: Schema,
  aliasUdfPaths?: Record<string, Path>
): LilacSchema {
  const lilacFields = lilacSchemaFieldFromField(rawSchema, aliasUdfPaths, []);

  if (!lilacFields.fields) {
    return {fields: {}, path: []};
  }

  // Convert the fields to LilacSchemaField
  return {fields: lilacFields.fields, path: []};
}

export function deserializeRow(rawRow: FieldValue, schema: LilacSchema): LilacValueNode {
  const fields = listFields(schema);
  const rootNode = lilacValueNodeFromRawValue(rawRow, fields, []);

  if (Array.isArray(rootNode)) {
    throw new Error('Expected row to have a single root node');
  }
  if (!rootNode) {
    throw new Error('Expected row to have children');
  }

  castLilacValueNode(rootNode)[VALUE_KEY] = null;
  castLilacValueNode(rootNode)[PATH_KEY] = [];
  castLilacValueNode(rootNode)[SCHEMA_FIELD_KEY] = schema;
  return rootNode;
}

/** List all fields as a flattend array */
export function listFields(field: LilacSchemaField | LilacSchema | undefined): LilacSchemaField[] {
  if (!field) return [];
  // Return the cached value if it exists.
  // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
  if (listFieldsCache.has(field)) return listFieldsCache.get(field)!;

  const result = [
    field,
    ...Object.values(field.fields || {}).flatMap(listFields),
    ...(field.repeated_field ? listFields(field.repeated_field) : [])
  ].filter(f => f.path.length > 0);

  // Cache the result
  listFieldsCache.set(field, result);
  return result;
}

/** List all values as a flattend array */
export function listValueNodes(row: LilacValueNode): LilacValueNode[] {
  // Return the cached value if it exists.
  // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
  if (listValueNodesCache.has(row)) return listValueNodesCache.get(row)!;

  let result: LilacValueNode[];
  if (Array.isArray(row)) result = [...row, ...row.flatMap(listValueNodes)];
  else {
    // Strip the internal properties
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const {[VALUE_KEY]: value, [PATH_KEY]: path, [SCHEMA_FIELD_KEY]: field, ...rest} = row;

    const childProperties = Object.values(rest || {});
    result = [...childProperties, ...childProperties.flatMap(v => listValueNodes(v))];
  }

  // Cache the result
  listValueNodesCache.set(row, result);
  return result;
}

/**
 * List all fields that are parent of the given field
 */
export function listFieldParents(field: LilacSchemaField, schema: LilacSchema): LilacSchemaField[] {
  const parents: LilacSchemaField[] = [];
  for (let i = 1; i < field.path.length; i++) {
    const path = field.path.slice(0, i);
    const parent = getField(schema, path);
    if (parent) parents.push(parent);
  }
  return parents;
}

/**
 * Get a field in schema by path
 */
export function getField(schema: LilacSchema, path: Path): LilacSchemaField | undefined {
  const list = listFields(schema);
  return list.find(field => pathIsMatching(field.path, path));
}

/**
 * Get the first value at the given path in a row
 */
export function getValueNode(row: LilacValueNode, path: Path): LilacValueNode | undefined {
  const list = listValueNodes(row);
  return list.find(value => pathIsMatching(path, L.path(value)));
}

/**
 * Get all values at the given path in a row
 */
export function getValueNodes(row: LilacValueNode, path: Path): LilacValueNode[] {
  const list = listValueNodes(row);
  return list.filter(value => pathIsMatching(path, L.path(value)));
}

/**
 * Determine if field is produced by a signal. We do this by walking the schema from the root to the
 * field, and checking if a parent has a signal.
 */
export function isSignalField(
  field: LilacSchemaField,
  schema: LilacSchemaField,
  hasSignalRootParent = false
): boolean {
  if (isSignalRootField(schema)) {
    hasSignalRootParent = true;
  }
  if (schema === field) return hasSignalRootParent;
  if (schema.fields != null) {
    return Object.values(schema.fields).some(f => isSignalField(field, f, hasSignalRootParent));
  } else if (schema.repeated_field != null) {
    return isSignalField(field, schema.repeated_field, hasSignalRootParent);
  }
  return false;
}

export function isSignalRootField(field: LilacSchemaField) {
  return !!field.signal;
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
function lilacSchemaFieldFromField(
  field: Field,
  aliasUdfPaths: Record<string, Path> | undefined,
  path: Path
): LilacSchemaField {
  const {fields, repeated_field, ...rest} = field;
  const lilacField: LilacSchemaField = {...rest, path: []};
  if (fields != null) {
    lilacField.fields = {};
    for (const [fieldName, field] of Object.entries(fields)) {
      const lilacChildField = lilacSchemaFieldFromField(field, aliasUdfPaths, [...path, fieldName]);
      lilacChildField.path = [...path, fieldName];
      lilacField.fields[fieldName] = lilacChildField;
    }
  }
  if (repeated_field != null) {
    const lilacChildField = lilacSchemaFieldFromField(repeated_field, aliasUdfPaths, [
      ...path,
      PATH_WILDCARD
    ]);
    lilacChildField.path = [...path, PATH_WILDCARD];
    lilacField.repeated_field = lilacChildField;
  }
  if (aliasUdfPaths != null) {
    const alias = Object.entries(aliasUdfPaths).find(([, aliasPath]) =>
      pathIncludes(path, aliasPath)
    )?.[0];
    if (alias) {
      lilacField.alias = [alias, ...path.slice(aliasUdfPaths[alias].length)];
    }
  }
  return lilacField;
}

function lilacValueNodeFromRawValue(
  rawFieldValue: FieldValue,
  fields: LilacSchemaField[],
  path: Path
): LilacValueNode {
  const field = fields.find(field => pathIsMatching(field.path, path));

  let ret: LilacValueNode = {};
  if (Array.isArray(rawFieldValue)) {
    ret = rawFieldValue.map((value, i) =>
      lilacValueNodeFromRawValue(value, fields, [...path, i.toString()])
    ) as Record<number, LilacValueNode>;
    castLilacValueNode(ret)[VALUE_KEY] = null;
    return ret;
  } else if (rawFieldValue != null && typeof rawFieldValue === 'object') {
    const {[VALUE_KEY]: value, ...rest} = rawFieldValue;

    ret = Object.entries(rest).reduce<Record<string, LilacValueNode>>((acc, [key, value]) => {
      acc[key] = lilacValueNodeFromRawValue(value, fields, [...path, key]);
      return acc;
    }, {});
    // TODO(nikhil,jonas): Fix this type cast.
    castLilacValueNode(ret)[VALUE_KEY] = value as LeafValue;
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

/** SignalInfo where `json_schema` is typed as `JSONSchema7`. */
export type SignalInfoWithTypedSchema = Omit<SignalInfo, 'json_schema'> & {
  json_schema: JSONSchema7;
};
