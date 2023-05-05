import { DataType, Field, Schema } from './fastapi_client';
import { castDataType, ENTITY_FEATURE_KEY, LILAC_COLUMN, Path, PATH_WILDCARD } from './schema';
import { mergeDeep } from './utils';

const VALUE_KEY = '__value';
const PATH_KEY = '__path';

export type LilacSchemaField = Field & {
  path: Path;
  // Overwrite the fields and repeated_field properties to be LilacSchemaField
  repeated_field?: LilacSchemaField;
  fields?: Record<string, LilacSchemaField>;
};
export type LilacSchema = Omit<LilacSchemaField, 'path'>;
// {
//   fields: Record<string, LilacSchemaField>;
// };

export type LilacItemNode = {
  [key: string | number]: LilacItemNode;
};

type LilacItemNodeCasted<D extends DataType = DataType> = {
  [VALUE_KEY]: castDataType<D>;
  [PATH_KEY]: Path;
};

function castLilacItemNode<D extends DataType = DataType>(
  node: LilacItemNode
): LilacItemNodeCasted<D> {
  return node as unknown as LilacItemNodeCasted;
}
// export type LilacItemNode<D extends DataType = DataType> = {
//   value: castDataType<D>;
//   children?: LilacItemNode[] | Record<string, LilacItemNode>;
//   path: Path;
// };

/**
 * Deserialize a raw schema response to a LilacSchema.
 */
export function deserializeSchema(rawSchema: Schema): LilacSchema {
  const lilacFields = lilacSchemaFieldFromField(rawSchema, []);

  if (!lilacFields.fields) {
    return { fields: {} };
  }

  let { [LILAC_COLUMN]: signalsFields, ...fields } = lilacFields.fields;

  // Merge the signal fields into the source fields
  if (signalsFields?.fields) {
    fields = mergeDeep(fields, signalsFields.fields);
  }

  // Convert the fields to LilacSchemaField
  return { fields };
}

export function deserializeRow(rawRow: object, schema: LilacSchema): LilacItemNode {
  // const fields = listFields(schema);

  const children = lilacItemNodeFromRawValues(rawRow, []);

  if (Array.isArray(children)) {
    throw new Error('Expected row to have a single root node');
  }
  if (!children) {
    throw new Error('Expected row to have children');
  }

  const { [LILAC_COLUMN]: signalValues, ...values } = children;

  let mergedChildren: LilacItemNode = values;
  if (signalValues) mergedChildren = mergeDeep(values, signalValues);
  castLilacItemNode(mergedChildren)[VALUE_KEY] = null;
  castLilacItemNode(mergedChildren)[PATH_KEY] = [];
  return mergedChildren;
}

/** List all fields as a flattend array */
export function listFields(schema: LilacSchemaField | LilacSchema): LilacSchemaField[] {
  return [
    ...Object.values(schema.fields || {}),
    ...Object.values(schema.fields || {}).flatMap(listFields),
    ...(schema.repeated_field ? [schema.repeated_field] : []),
    ...(schema.repeated_field ? listFields(schema.repeated_field) : [])
  ];
}

/** List all values as a flattend array */
export function listValues(row: LilacItemNode): LilacItemNode[] {
  if (Array.isArray(row)) return [...row, ...row.flatMap(listValues)];
  else {
    const { [VALUE_KEY]: value, [PATH_KEY]: path, ...rest } = row;

    const childProperties = Object.values(rest || {});
    return [...childProperties, ...childProperties.flatMap((v) => listValues(v))];
  }
}

/**
 * Get a field in schema by path
 */
export function getField(schema: LilacSchema, path: Path): LilacSchemaField | undefined {
  const list = listFields(schema);
  return list.find((field) => field.path.join('.') === path.join('.'));
}

export function getValue(row: LilacItemNode, _path: Path): LilacItemNode | undefined {
  const list = listValues(row);
  return list.find((value) => path(value).join('.') === _path.join('.'));
}

export function path(value: LilacItemNode): Path {
  if (!value) throw new Error('Value is undefined');
  return castLilacItemNode(value)[PATH_KEY];
}

export function value<D extends DataType = DataType>(value: LilacItemNode): castDataType<D> {
  if (!value) throw new Error('Value is undefined');
  return castLilacItemNode(value)[VALUE_KEY] as castDataType<D>;
}

export function field(value: LilacItemNode, schema: LilacSchema): LilacSchemaField | undefined {
  const _path = path(value);
  return getField(schema, _path);
}
export function dtype(value: LilacItemNode, schema: LilacSchema): DataType | undefined {
  const _field = field(value, schema);
  return _field?.dtype;
}
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
  return lilacField;
}

function lilacItemNodeFromRawValues(
  rawValue: any,
  // fields: LilacSchemaField[],
  path: Path
): LilacItemNode {
  if (Array.isArray(rawValue)) {
    const ret: LilacItemNode = rawValue.map((value) =>
      lilacItemNodeFromRawValues(value, [...path, PATH_WILDCARD])
    ) as Record<number, LilacItemNode>;
    castLilacItemNode(ret)[PATH_KEY] = path;
    castLilacItemNode(ret)[VALUE_KEY] = null;
    return ret;
  } else if (typeof rawValue === 'object') {
    const { [ENTITY_FEATURE_KEY]: entityValue, ...rest } = rawValue;

    const ret: LilacItemNode = Object.entries(rest).reduce<Record<string, LilacItemNode>>(
      (acc, [key, value]) => {
        acc[key] = lilacItemNodeFromRawValues(value, [...path, key]);
        return acc;
      },
      {}
    );
    castLilacItemNode(ret)[PATH_KEY] = path;
    castLilacItemNode(ret)[VALUE_KEY] = entityValue || null;
    return ret;
  } else {
    const ret: LilacItemNode = {};
    castLilacItemNode(ret)[PATH_KEY] = path;
    castLilacItemNode(ret)[VALUE_KEY] = rawValue;
    return ret;
  }
}
