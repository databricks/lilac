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

type ILilacField = {
  readonly children?: Record<string, ILilacField>;
  readonly dataType: LilacDataType;
  readonly path: Path;

  readonly derivedFromPath: Path;

  /** Is the field produced by a signal */
  readonly isSignalField: boolean;

  readonly isSourceField: boolean;

  readonly hasChildren: () => boolean;
};

type ILilacFieldWithValue = Omit<ILilacField, 'children'> & {
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

export function LilacField(schema: Schema, path: Path): ILilacField;
export function LilacField(
  schema: Schema,
  path: Path,
  rowFieldValue?: FieldValue
): ILilacFieldWithValue;
export function LilacField<T extends FieldValue>(
  schema: Schema,
  path: Path,
  rowFieldValue?: T
): ILilacField | ILilacFieldWithValue {
  const schemaField = getFieldByPath(schema, path);

  if (!schemaField) throw new Error('Field not found for path ' + serializePath(path));

  if (schemaField.dtype === 'list') {
    return LilacField(schema, [...path, PATH_WILDCARD], rowFieldValue);
  }

  if (schemaField.is_entity) {
    return LilacField(schema, [...path, '__entity__'], rowFieldValue);
  }

  let dataType: LilacDataType = schemaField.dtype || 'struct';
  if (path.at(-1) === PATH_WILDCARD || serializePath(path).endsWith('.*.__entity__')) {
    dataType = `${dataType}[]`;
  }

  const ret: ILilacField = {
    dataType,
    isSignalField: path.at(0) === LILAC_COLUMN,
    isSourceField: path.at(0) !== LILAC_COLUMN,
    path,
    derivedFromPath: schemaField.derived_from,

    hasChildren: function () {
      return !!this.children;
    }
  };


  if (rowFieldValue === undefined) {
    return {...ret, children: constructChildren(schema, path, undefined)};
  } else {
    const valueField = getValueByPath(rowFieldValue, path);
    return {
      ...ret,
      children: constructChildren(schema, path, rowFieldValue),
      value: valueField
    } satisfies ILilacFieldWithValue;
  }

  // if (!dataType) throw new Error('dataType is undefined' + serializePath(path));
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
  const res = LilacField(schema, [], row);

  const uuidColumn = res.children?.[UUID_COLUMN];

  return {
    ...res,
    id: (uuidColumn?.dataType === 'string' && uuidColumn.value) || undefined
  };
}

/**
 * Initiates Fields for children of a given path using the initiator function
 */

type LilacFieldFromFieldValue<T extends FieldValue | undefined> = T extends FieldValue
  ? ILilacFieldWithValue
  : ILilacField;


function constructChildren<F extends FieldValue | undefined>(
  schema: Schema,
  path: Path,
  rowFieldValue: F
): (Record<string, LilacFieldFromFieldValue<F>> ) |  undefined {
  const field = getFieldByPath(schema, path);
  const annotationField = getFieldByPath(schema, [LILAC_COLUMN, ...path]);

  const children: Record<string, LilacFieldFromFieldValue<F>> = {};

  if (field?.fields) {
    for (const fieldName of Object.keys(field.fields)) {
      // Treat __lilac__ differently
      if (!path.length && fieldName === LILAC_COLUMN) {
        continue;
      }
      children[fieldName] = LilacField(schema, [...path, fieldName], rowFieldValue);
    }
  }

  // Add annotation fields
  for (const fieldName of Object.keys(annotationField?.fields || {})) {
    if (!children[fieldName]) {
      children[fieldName] = LilacField(schema, [LILAC_COLUMN, ...path, fieldName], rowFieldValue);
    }
  }

  if (Object.keys(children).length === 0) {
    return undefined;
  }

  return children;
}
