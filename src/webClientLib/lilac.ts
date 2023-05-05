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
type ILilacField = Readonly<
  {
    children?: ILilacFieldChildren;

    // dataType: LilacDataType;
    path: Path;

    derivedFromPath: Path;

    /** Is the field produced by a signal */
    isSignalField: boolean;

    isSourceField: boolean;

    hasChildren: () => boolean;

    queryPath: (path: Path, relative?: boolean) => ILilacField | undefined;

    getDerivedField: () => ILilacField | undefined;
  } & (
    | {
        dataType: DataType;
        value: null;
      }
    | {
        dataType: 'string';
        value: LeafValue<'string'>;
      }
    | {
        dataType: DataTypeNumber;
        value: LeafValue<DataTypeNumber>;
      }
    | {
        dataType: 'string_span';
        value: LeafValue<'string_span'>;
      }
    | {
        dataType: 'boolean';
        value: LeafValue<'boolean'>;
      }
    | {
        dataType: 'time' | 'date' | 'timestamp' | 'interval' | 'binary';
        value: LeafValue<'time' | 'date' | 'timestamp' | 'interval' | 'binary'>;
      }
    | {
        dataType: 'struct';
        value: LeafValue<'struct'>;
      }
    | {
        dataType: `${Exclude<DataType, 'list'>}[]`;
        value: LeafValue<`${Exclude<DataType, 'list'>}[]`>;
      }
  )
>;

// type ILilacFieldNoValue = Omit<ILilacField, 'value' | 'children'> & {
//   children?: Record<string, ILilacFieldNoValue>;
// };

export function LilacField<T extends FieldValue>(
  schema: Schema,
  path: Path,
  rowFieldValue?: T,
  _rootField?: ILilacField
): ILilacField {
  const schemaField = getFieldByPath(schema, path);

  if (!schemaField) throw new Error('Field not found for path ' + serializePath(path));

  // If the dtype is a list, return the child field instead
  if (schemaField.dtype === 'list') {
    return LilacField(schema, [...path, PATH_WILDCARD], rowFieldValue, _rootField);
  }

  // If field is an entity, return the entity field instead
  if (schemaField.is_entity) {
    return LilacField(schema, [...path, '__entity__'], rowFieldValue, _rootField);
  }

  let dataType: LilacDataType = schemaField.dtype || 'struct';
  if (path.at(-1) === PATH_WILDCARD || serializePath(path).endsWith('.*.__entity__')) {
    dataType = `${dataType}[]`;
  }

  const ret: Writeable<ILilacField> = {
    isSignalField: path.at(0) === LILAC_COLUMN,
    isSourceField: path.at(0) !== LILAC_COLUMN,
    path,
    derivedFromPath: schemaField.derived_from as string[],

    dataType,
    value: null,

    hasChildren: function () {
      return !!this.children;
    },

    queryPath: function (path: Path, relative: boolean) {
      if (relative) {
        if (path.length) {
          if (!this.children?.[path[0]]) return undefined;
          return this.children[path[0]].queryPath(path.slice(1), true);
        } else {
          return this;
        }
      } else {
        console.log(path, this, _rootField);
        return (_rootField || this)?.queryPath(path, true);
      }
    },

    getDerivedField: function () {
      if (!this.derivedFromPath) return undefined;
      return this.queryPath(this.derivedFromPath, false);
    }
  };

  const valueField = getValueByPath(rowFieldValue, path);
  ret.children = constructChildren(schema, path, rowFieldValue, _rootField || ret);
  ret.value = valueField;

  return ret;
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

export function LilacSchema(schema: Schema) {
  return LilacField(schema, []);
}

type ILilacRow = ILilacField & {
  /** id of row */
  readonly id?: string;
};

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

// type LilacFieldFromFieldValue<T extends FieldValue | undefined> = T extends FieldValue
//   ? ILilacField
//   : ILilacFieldNoValue;

type ILilacFieldChildren = { [key: string]: ILilacField };

type Writeable<T> = { -readonly [P in keyof T]: T[P] };

function constructChildren(
  schema: Schema,
  path: Path,
  rowFieldValue: FieldValue | undefined,
  _rootField: ILilacField
): ILilacFieldChildren | undefined {
  const field = getFieldByPath(schema, path);
  const annotationField = getFieldByPath(schema, [LILAC_COLUMN, ...path]);

  const children: ILilacFieldChildren = {};

  if (field?.fields) {
    for (const fieldName of Object.keys(field.fields)) {
      // Treat __lilac__ differently
      if (!path.length && fieldName === LILAC_COLUMN) {
        continue;
      }
      children[fieldName] = LilacField(schema, [...path, fieldName], rowFieldValue, _rootField);
    }
  }

  // Add annotation fields
  for (const fieldName of Object.keys(annotationField?.fields || {})) {
    if (!children[fieldName]) {
      children[fieldName] = LilacField(
        schema,
        [LILAC_COLUMN, ...path, fieldName],
        rowFieldValue,
        _rootField
      );
    }
  }

  if (Object.keys(children).length === 0) {
    return undefined;
  }

  return children;
}
