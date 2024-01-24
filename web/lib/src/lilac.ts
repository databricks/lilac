import type {JSONSchema7} from 'json-schema';
import type {
  BinaryFilter,
  ClusterInfo,
  ConceptSearch,
  DataType,
  Field,
  KeywordSearch,
  ListFilter,
  MapInfo,
  MetadataSearch,
  Schema,
  SelectRowsSchemaResult,
  SemanticSearch,
  Signal,
  SignalInfo,
  StringFilter,
  UnaryFilter
} from '../fastapi_client';
import {
  DELETED_LABEL_KEY,
  PATH_WILDCARD,
  SPAN_KEY,
  VALUE_KEY,
  pathIsMatching,
  type DataTypeCasted,
  type FieldValue,
  type LeafValue,
  type Path
} from './schema';

export const PATH_KEY = '__path__';
export const SCHEMA_FIELD_KEY = '__field__';
// The search type is not an explicitly exported type so we extract the type from the different
// search types automatically for type-safety.
export type SearchType = Exclude<
  (ConceptSearch | SemanticSearch | KeywordSearch | MetadataSearch)['type'],
  undefined
>;
export type Search = ConceptSearch | SemanticSearch | KeywordSearch | MetadataSearch;

export type Op = BinaryFilter['op'] | StringFilter['op'] | UnaryFilter['op'] | ListFilter['op'];
export type Filter = BinaryFilter | StringFilter | UnaryFilter | ListFilter;

export type LilacField<S extends Signal = Signal> = Field & {
  path: Path;
  parent?: LilacField;
  // Overwrite the fields and repeated_field properties to be LilacField
  repeated_field?: LilacField;
  fields?: Record<string, LilacField>;
  // Overwrite signal type from generic
  signal?: S;
};
export interface LilacSchema extends LilacField {
  fields: NonNullable<LilacField['fields']>;
}
export type LilacSelectRowsSchema = SelectRowsSchemaResult & {
  schema: LilacSchema;
};

export type LilacValueNode = {
  readonly [key: string | number]: LilacValueNode;
};

/**
 * Internal type for a LilacValueNode casted with internal properties.
 */
export type LilacValueNodeCasted<D extends DataType['type'] = DataType['type']> = {
  /** Holds the actual value of the node */
  [VALUE_KEY]?: DataTypeCasted<D>;
  [SPAN_KEY]?: DataTypeCasted<'string_span'>;
  /** Holds the path property of the node */
  [PATH_KEY]: Path;
  /** Holds a reference to the schema field */
  [SCHEMA_FIELD_KEY]?: LilacField | undefined;
  [metadata: string]: unknown;
};

export function valueAtPath(item: LilacValueNode, path: Path): LilacValueNode | null {
  if (item == null) throw Error('Item is null.');
  if (path.length === 0) {
    return item;
  }
  const [key, ...rest] = path;
  if (item[key] == null) {
    return null;
  }
  return valueAtPath(item[key], rest);
}

export function valuesAtPath(
  item: LilacValueNode | LilacValueNode[],
  path: Path
): LilacValueNode[] {
  if (item == null) {
    return [];
  }
  const [key, ...rest] = path;
  if (key == PATH_WILDCARD) {
    return (item as LilacValueNode[]).flatMap(v => valuesAtPath(v, rest));
  }
  item = item as LilacValueNode;
  if (rest.length === 0) {
    return [item[key]];
  }
  return valuesAtPath(item[key], rest);
}

/**
 * Cast a value node to an internal value node
 */
function castLilacValueNode<D extends DataType['type'] = DataType['type']>(
  node: LilacValueNode
): LilacValueNodeCasted<D> {
  return node as unknown as LilacValueNodeCasted;
}

/**
 * Deserialize a raw schema response to a LilacSchema, a client-side representation of the data
 * schema.
 */
export function deserializeSchema(rawSchema: Schema): LilacSchema {
  const lilacFields = deserializeField(rawSchema as Field);

  if (!lilacFields.fields) {
    return {fields: {}, path: []};
  }

  // Convert the fields to LilacField
  return {fields: lilacFields.fields, path: []};
}

export function deserializeRow(
  rawRow: FieldValue,
  schema: LilacSchema | LilacField | undefined
): LilacValueNode {
  const fields = childFields(schema);
  const rootNode = lilacValueNodeFromRawValue(rawRow, fields, []);

  if (!rootNode) {
    throw new Error('Expected row to have children');
  }

  if (Array.isArray(rootNode)) {
    return rootNode;
  }

  castLilacValueNode(rootNode)[SPAN_KEY] = null;
  castLilacValueNode(rootNode)[VALUE_KEY] = null;
  castLilacValueNode(rootNode)[PATH_KEY] = [];
  castLilacValueNode(rootNode)[SCHEMA_FIELD_KEY] = schema;
  return rootNode;
}

/** List all fields as a flattened array */
export function childFields(field: LilacField | LilacSchema | undefined): LilacField[] {
  if (field == null) return [];
  const result = [
    field,
    ...Object.values(field.fields || {}).flatMap(childFields),
    ...(field.repeated_field ? childFields(field.repeated_field) : [])
  ].filter(f => f.path.length > 0);

  return result;
}

/** Get all field petals (nodes with values). */
export function petals(field: LilacField | LilacSchema | undefined | null): LilacField[] {
  if (field == null) return [];
  return childFields(field).filter(f => f.dtype != null);
}

export function getFieldsByDtype(dtype: DataType, schema?: LilacSchema | LilacField): LilacField[] {
  if (schema == null) {
    return [];
  }

  const allFields = schema ? childFields(schema) : [];
  return allFields.filter(f => f.dtype == dtype);
}

/** List all values as a flattend array */
export function listValueNodes(row: LilacValueNode): LilacValueNode[] {
  let result: LilacValueNode[];
  if (Array.isArray(row)) {
    result = [...row, ...row.flatMap(listValueNodes)];
  } else {
    // Strip the internal properties
    /* eslint-disable @typescript-eslint/no-unused-vars */
    const {
      [SPAN_KEY]: span,
      [VALUE_KEY]: value,
      [PATH_KEY]: path,
      [SCHEMA_FIELD_KEY]: field,
      ...rest
    } = row;
    /* eslint-enable @typescript-eslint/no-unused-vars */
    const childProperties = Object.values(rest || {});
    result = [];
    for (const childProperty of childProperties) {
      if (Array.isArray(childProperty)) {
        result = [...result, childProperty];
        for (const el of childProperty) {
          result = [...result, el, ...listValueNodes(el)];
        }
      } else {
        result = [...result, childProperty, ...listValueNodes(childProperty)];
      }
    }
  }

  return result;
}

/**
 * List all fields that are parent of the given field
 */
export function listFieldParents(field: LilacField, schema: LilacSchema): LilacField[] {
  const parents: LilacField[] = [];
  for (let i = 1; i < field.path.length; i++) {
    const path = field.path.slice(0, i);
    const parent = getField(schema, path);
    if (parent) parents.push(parent);
  }
  return parents;
}

/**
 * Get a field in schema by path.
 */
export function getField(schema: LilacSchema, path: Path): LilacField | undefined {
  const list = childFields(schema);
  return list.find(field => pathIsMatching(field.path, path));
}

/**
 * Get all values at the given path in a row
 */
export function getValueNodes(row: LilacValueNode, path: Path): LilacValueNode[] {
  const list = listValueNodes(row);
  return list.filter(value => pathIsMatching(path, L.path(value)));
}

/** Determine if a field is produced by a signal. */
export function isSignalField(field: LilacField): boolean {
  return getSignalInfo(field) != null;
}

/** If a field is produced by a signal, it returns the signal information. Otherwise returns null. */
export function getSignalInfo(field: LilacField): Signal | null {
  if (field.signal) {
    return field.signal;
  }
  if (field.parent) {
    return getSignalInfo(field.parent);
  }
  return null;
}

/** True if the field was the root field produced by a signal. */
export function isSignalRootField(field: LilacField) {
  return field.signal != null;
}

/** Determine if a field is produced by a map. */
export function isMapField(field: LilacField): boolean {
  return getMapInfo(field) != null;
}

/** If a field is produced by a map, it returns the map information. Otherwise returns null. */
export function getMapInfo(field: LilacField): MapInfo | null {
  if (field.map != null) {
    return field.map;
  }
  if (field.parent != null) {
    return getMapInfo(field.parent);
  }
  return null;
}

/** True if the field was the root field produced by a map. */
export function isMapRootField(field: LilacField) {
  return field.map != null;
}

/** If a field is produced by a map, it returns the map information. Otherwise returns null. */
export function getClusterInfo(field: LilacField): ClusterInfo | null {
  if (field.cluster) {
    return field.cluster;
  }
  if (field.parent) {
    return getClusterInfo(field.parent);
  }
  return null;
}

/** Determine if a field is produced by a clusterer. */
export function isClusterField(field: LilacField): boolean {
  return getClusterInfo(field) != null;
}

/** True if the field was the root field produced by a map. */
export function isClusterRootField(field: LilacField) {
  // TODO(smilkov): Add a special bit to the field to indicate that it is a cluster root field.
  return field.cluster != null;
}

/** Determine if a field is produced by a label. */
export function isLabelRootField(field: LilacField) {
  return field.label != null;
}

/** If a field is produced by a label, returns the label name. Otherwise returns null. */
export function getLabel(field: LilacField): string | null {
  if (field.label) {
    return field.label;
  }
  if (field.parent) {
    return getLabel(field.parent);
  }
  return null;
}

export function isLabelField(field: LilacField): boolean {
  return getLabel(field) != null;
}

/** Determine if a field is produced by a embedding. */
export function isEmbeddingField(field: LilacField): boolean {
  return hasSignalParent(field) && hasEmbeddingChild(field);
}

function hasSignalParent(field: LilacField): boolean {
  const parentHasSignal = field.parent != null && field.parent.signal != null;
  if (parentHasSignal) {
    return true;
  }
  if (field.parent) {
    return hasSignalParent(field.parent);
  }
  return false;
}

function hasEmbeddingChild(field: LilacField): boolean {
  return childFields(field).some(f => f.dtype?.type === 'embedding');
}

export function getSchemaLabels(schema: LilacSchema | LilacField): string[] {
  return childFields(schema)
    .map(f => f.label)
    .filter(l => l != null && l !== DELETED_LABEL_KEY) as string[];
}

export function getRowLabels(node: LilacValueNode): string[] {
  return listValueNodes(node)
    .map(n => L.field(n)?.label)
    .filter(l => l != null) as string[];
}

export const L = {
  path: (item: LilacValueNode): Path | undefined => {
    if (!item) return undefined;
    const path = castLilacValueNode(item)[PATH_KEY];
    if (path == null) throw Error(`Item does not have a path defined: ${JSON.stringify(item)}`);
    return path;
  },
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  value: <D extends DataType['type']>(item: LilacValueNode, dtype?: D): DataTypeCasted<D> => {
    if (!item) return null;
    return castLilacValueNode(item)[VALUE_KEY] as DataTypeCasted<D>;
  },
  span: (
    item: LilacValueNode | LilacValueNodeCasted
  ): DataTypeCasted<'string_span'> | undefined => {
    item = item as LilacValueNode;
    if (!item) return null;
    const spanItem = castLilacValueNode<'string_span'>(item);
    return spanItem[SPAN_KEY] || L.value<'string_span'>(item);
  },
  field: (value: LilacValueNode): LilacField | undefined => {
    if (!value) return undefined;
    return castLilacValueNode(value)[SCHEMA_FIELD_KEY];
  },
  dtype: (value: LilacValueNode): DataType | undefined | null => {
    const _field = L.field(value);
    return _field?.dtype;
  }
};

/**
 * Convert raw schema field to LilacField.
 * Adds path attribute to each field
 */
export function deserializeField(field: Field, path: Path = []): LilacField {
  const {fields, repeated_field, ...rest} = field;
  const lilacField: LilacField = {...rest, path: []} as LilacField;
  if (fields != null) {
    lilacField.fields = {};
    for (const [fieldName, field] of Object.entries(fields)) {
      const lilacChildField = deserializeField(field, [...path, fieldName]);
      lilacChildField.path = [...path, fieldName];
      lilacChildField.parent = lilacField;
      lilacField.fields[fieldName] = lilacChildField;
    }
  }
  if (repeated_field != null) {
    const lilacChildField = deserializeField(repeated_field, [...path, PATH_WILDCARD]);
    lilacChildField.path = [...path, PATH_WILDCARD];
    lilacChildField.parent = lilacField;
    lilacField.repeated_field = lilacChildField;
  }
  return lilacField;
}

function lilacValueNodeFromRawValue(
  rawFieldValue: FieldValue,
  fields: LilacField[],
  path: Path
): LilacValueNode {
  const field = fields.find(field => pathIsMatching(field.path, path));

  let ret: LilacValueNode = {};
  if (Array.isArray(rawFieldValue)) {
    ret = rawFieldValue.map((value, i) =>
      lilacValueNodeFromRawValue(value, fields, [...path, i.toString()])
    ) as Record<number, LilacValueNode>;
    castLilacValueNode(ret)[VALUE_KEY] = null;
    castLilacValueNode(ret)[PATH_KEY] = path;
    castLilacValueNode(ret)[SCHEMA_FIELD_KEY] = field;
    return ret;
  } else if (rawFieldValue != null && typeof rawFieldValue === 'object') {
    const {[VALUE_KEY]: value, [SPAN_KEY]: span, ...rest} = rawFieldValue;

    ret = Object.entries(rest).reduce<Record<string, LilacValueNode>>((acc, [key, value]) => {
      acc[key] = lilacValueNodeFromRawValue(value, fields, [...path, key]);
      return acc;
    }, {});
    // TODO(nikhil,jonas): Fix this type cast.
    castLilacValueNode(ret)[VALUE_KEY] = value as LeafValue;
    castLilacValueNode(ret)[SPAN_KEY] = span as DataTypeCasted<'string_span'>;
  } else {
    castLilacValueNode(ret)[VALUE_KEY] = rawFieldValue;
  }
  castLilacValueNode(ret)[PATH_KEY] = path;
  castLilacValueNode(ret)[SCHEMA_FIELD_KEY] = field;
  return ret;
}

/** SignalInfo where `json_schema` is typed as `JSONSchema7`. */
export type SignalInfoWithTypedSchema = Omit<SignalInfo, 'json_schema'> & {
  json_schema: JSONSchema7;
};
