import { DatasetsService, DataType, Schema } from './fastapi_client';
import {
  DataTypeNumber,
  FieldValue,
  getFieldByPath,
  getValueByPath,
  LeafValue,
  LilacDataType,
  LILAC_COLUMN,
  Path,
  PATH_WILDCARD,
  serializePath,
  UUID_COLUMN
} from './schema';

export class Lilac {
  async selectRows(schema: Schema, ...args: Parameters<typeof DatasetsService.selectRows>) {
    const response = await DatasetsService.selectRows(...args);
    return LilacSelectRowsResponse(response, schema);
  }
}

/**
 * Represents a field in a dataset
 */

interface ILilacField {
  readonly children?: Record<string, ILilacField>;
  readonly dataType: LilacDataType;
  readonly path: Path;

  readonly derivedFromPath: Path;

  /** Is the field produced by a signal */
  readonly isSignalField: boolean;

  readonly isSourceField: boolean;

  readonly hasChildren: () => boolean;
}

export function LilacField(schema: Schema, path: Path, skipChildren = false): ILilacField {
  const schemaField = getFieldByPath(schema, path);

  if (!schemaField) throw new Error('Field not found for path ' + serializePath(path));

  if (schemaField.dtype === 'list') {
    return LilacField(schema, [...path, PATH_WILDCARD], skipChildren);
  }

  if (schemaField.is_entity) {
    return LilacField(schema, [...path, '__entity__'], skipChildren);
  }

  let dataType: LilacDataType = schemaField.dtype || 'struct';
  if (path.at(-1) === PATH_WILDCARD || serializePath(path).endsWith('.*.__entity__')) {
    dataType = `${dataType}[]`;
  }

  //   schemaField = schemaField.fields?.__entity__;
  //   if(!schemaField)
  //     throw new Error('Entity field not present for path ' + serializePath(path));
  //   dataType = schemaField.dtype || 'struct';
  // }

  return {
    children: !skipChildren ? constructChildren(schema, path, LilacField) : undefined,
    dataType,
    isSignalField: path.at(0) === LILAC_COLUMN,
    isSourceField: path.at(0) !== LILAC_COLUMN,
    path,
    derivedFromPath: schemaField.derived_from,

    hasChildren: function () {
      return !!this.children;
    }
  };
}

type ILilacFieldValue = {
  readonly children?: Record<string, ILilacFieldWithValue>;
} & (
  | {
      readonly dataType: 'string';
      readonly value: LeafValue<'string'>;
    }
  | {
      readonly dataType: DataTypeNumber;
      readonly value: LeafValue<DataTypeNumber>;
    }
  | {
      readonly dataType: 'string_span';
      readonly value: LeafValue<'string_span'>;
    }
  | {
      readonly dataType: 'boolean';
      readonly value: LeafValue<'boolean'>;
    }
  | {
      readonly dataType: 'time' | 'date' | 'timestamp' | 'interval' | 'binary';
      readonly value: LeafValue<'time' | 'date' | 'timestamp' | 'interval' | 'binary'>;
    }
  | {
      readonly dataType: 'struct';
      readonly value: LeafValue<'struct'>;
    }
  | {
      readonly dataType: `${Exclude<DataType, 'list'>}[]`;
      readonly value: LeafValue<`${Exclude<DataType, 'list'>}[]`>;
    }
);

type ILilacFieldWithValue = Omit<ILilacField, 'dataType' | 'children'> & ILilacFieldValue;

function LilacFieldWithValue(schema: Schema, path: Path, row: FieldValue): ILilacFieldWithValue {
  const schemaRes = LilacField(schema, path, true);

  const valueField = getValueByPath(row, schemaRes.path);
  const dataType = schemaRes.dataType;

  if (!dataType) throw new Error('dataType is undefined' + serializePath(path));

  const value = valueField as LeafValue<typeof dataType>;

  return {
    ...schemaRes,
    dataType,
    value,
    children: constructChildren(schema, path, (s, p) => LilacFieldWithValue(s, p, row))

    // TODO remove as
  } as ILilacFieldWithValue;
}

/**
 * Represents the result of a selectRows call.
 */
export function LilacSelectRowsResponse(
  response: Awaited<ReturnType<typeof DatasetsService.selectRows>>,
  schema: Schema
) {
  return {
    rows: response.map((row) => LilacRow(schema, row))
  };
}

export function LilacSchema(schema: Schema): ILilacField {
  return LilacField(schema, []);
}

interface ILilacRow {
  /** Child fields of row */
  readonly children?: Record<string, ILilacFieldWithValue>;
  /** id of row */
  readonly id?: string;
}

/**
 * Represent a row in a dataset
 */
export function LilacRow(
  schema: Schema,
  row: Awaited<ReturnType<typeof DatasetsService.selectRows>>[number]
): ILilacRow {
  // function idColumn
  const res = LilacFieldWithValue(schema, [], row);

  const uuidColumn = res.children?.[UUID_COLUMN];

  return {
    ...res,
    id: (uuidColumn?.dataType === 'string' && uuidColumn.value) || undefined
  };
}

function constructChildren<T>(
  schema: Schema,
  path: Path,
  initiator: (schema: Schema, path: Path) => T
) {
  const field = getFieldByPath(schema, path);
  const annotationField = getFieldByPath(schema, [LILAC_COLUMN, ...path]);

  const children: Record<string, T> = {};

  if (field?.fields) {
    for (const fieldName of Object.keys(field.fields)) {
      // Treat __lilac__ differently
      if (!path.length && fieldName === LILAC_COLUMN) {
        continue;
      }
      children[fieldName] = initiator(schema, [...path, fieldName]);
    }
  }

  // Add annotation fields
  for (const fieldName of Object.keys(annotationField?.fields || {})) {
    if (!children[fieldName]) {
      children[fieldName] = initiator(schema, [LILAC_COLUMN, ...path, fieldName]);
    }
  }

  if (Object.keys(children).length === 0) {
    return undefined;
  }

  return children;
}
