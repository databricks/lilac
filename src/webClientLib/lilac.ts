import { DatasetsService, DataType, Field, Schema } from './fastapi_client';
import {
  FieldValue,
  getFieldByPath,
  getValueByPath,
  isFloat,
  isInteger,
  LeafValue,
  LILAC_COLUMN,
  Path,
  UUID_COLUMN
} from './schema';

export class Lilac {
  async selectRows(schema: Schema, ...args: Parameters<typeof DatasetsService.selectRows>) {
    const response = await DatasetsService.selectRows(...args);
    return new LilacSelectRowsResponse(response, schema);
  }
}

/**
 * Represents a field in a dataset
 */

// export function LilacField(schema: Schema, path: Path): ILilacField {

// }
export class LilacField {
  constructor(protected schema: Schema, public path: Path) {}
  /**
   * Returns the children of this field, if any.
   */
  get children(): Record<string, LilacField> | undefined {
    return this._constructChildren((schema, path) => new LilacField(schema, path));
  }

  get hasChildren(): boolean {
    return !!this._schemaField.fields;
  }

  get dataType(): DataType | undefined {
    return this._schemaField.dtype;
  }

  isString() {
    return this.dataType === 'string';
  }

  isNumber() {
    return this.dataType && (isFloat(this.dataType) || isInteger(this.dataType)) ? true : false;
  }

  protected get _schemaField(): Field {
    return getFieldByPath(this.schema, this.path);
  }

  protected _constructChildren<T>(initiator: (schema: Schema, path: Path) => T) {
    const field = this._schemaField;
    if (field.fields) {
      const children: Record<string, T> = {};
      for (const fieldName of Object.keys(field.fields)) {
        // Treat __lilac__ differently
        if (!this.path.length && fieldName === LILAC_COLUMN) {
          continue;
        }
        children[fieldName] = initiator(this.schema, [...this.path, fieldName]);
      }
      return children;
    }
    return undefined;
  }
}

export class LilacFieldWithValue extends LilacField {
  constructor(schema: Schema, path: Path, private row: FieldValue) {
    super(schema, path);
  }

  /**
   * Get the value of leaf field
   */
  get value(): LeafValue | undefined {
    if (!this.hasChildren) {
      return undefined;
    }
    if (Array.isArray(this._valueField)) {
      throw new Error('Expected a leaf value, got an array.');
    } else if (typeof this._valueField === 'object') {
      throw new Error('Expected a leaf value, got an object.');
    }
    return this._valueField;
  }

  get children(): Record<string, LilacFieldWithValue> | undefined {
    return this._constructChildren(
      (schema, path) => new LilacFieldWithValue(schema, path, this.row)
    );
  }

  isString(): this is this & { value: string } {
    return super.isString();
  }
  isNumber(): this is this & { value: number } {
    return super.isNumber();
  }

  get _valueField(): FieldValue {
    return getValueByPath(this.row, this.path);
  }
}

// interface ILilacField {
//   children?: Record<string, LilacField>;
// }

// type ILilacFieldWithValue = ILilacField &
//   (
//     | {
//         value: string;
//         dataType: 'string';
//       }
//     | {
//         value: number;
//         dataType: 'number';
//       }
//   );

/**
 * Represents the result of a selectRows call.
 */
export class LilacSelectRowsResponse {
  rows: LilacRow[];
  constructor(
    private response: Awaited<ReturnType<typeof DatasetsService.selectRows>>,
    private schema: Schema
  ) {
    this.rows = response.map((row) => new LilacRow(schema, row));
  }
}

/**
 * Represents a dataset schema without data
 */
export class LilacSchema extends LilacField {
  constructor(schema: Schema) {
    super(schema, []);
  }
}

/**
 * Represent a row in a dataset
 */
export class LilacRow extends LilacFieldWithValue {
  constructor(schema: Schema, row: Awaited<ReturnType<typeof DatasetsService.selectRows>>[number]) {
    super(schema, [], row);
  }

  get id(): string | undefined {
    const column = this.children?.[UUID_COLUMN];
    if (!column) return;
    if (column.isString()) {
      return column.value;
    }
  }
}
