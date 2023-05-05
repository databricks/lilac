import { describe, expect, it } from 'vitest';
import { Schema } from './fastapi_client';
import {
  deserializeRow,
  deserializeSchema,
  dtype,
  field,
  getField,
  getValue,
  listFields,
  listValues,
  path,
  value
} from './lilac';
import { ENTITY_FEATURE_KEY } from './schema';

const MANIFEST_SCHEMA_FIXTURE: Schema = {
  fields: {
    title: {
      dtype: 'string'
    },
    comment_text: {
      dtype: 'string'
    },
    complex_field: {
      dtype: 'struct',
      fields: {
        propertyA: {
          dtype: 'string'
        },
        propertyB: {
          dtype: 'string'
        }
      }
    },
    tags: {
      dtype: 'list',
      repeated_field: {
        dtype: 'string'
      }
    },
    complex_list_of_struct: {
      dtype: 'list',
      repeated_field: {
        dtype: 'struct',
        fields: {
          propertyA: {
            dtype: 'string'
          },
          propertyB: {
            dtype: 'string'
          }
        }
      }
    },
    __rowid__: {
      dtype: 'string'
    },
    __lilac__: {
      fields: {
        comment_text: {
          fields: {
            pii: {
              fields: {
                emails: {
                  repeated_field: {
                    fields: {},
                    dtype: 'string_span',
                    is_entity: true,
                    derived_from: ['comment_text']
                  },
                  dtype: 'list',
                  derived_from: ['comment_text']
                }
              },
              dtype: 'struct',
              signal_root: true,
              derived_from: ['comment_text']
            }
          },
          dtype: 'struct'
        },
        complex_field: {
          dtype: 'struct',
          fields: {
            propertyA: {
              dtype: 'struct',
              fields: {
                text_statistics: {
                  fields: {
                    num_characters: {
                      dtype: 'int32',
                      derived_from: ['review']
                    }
                  },
                  dtype: 'struct',
                  signal_root: true,
                  derived_from: ['review']
                }
              }
            }
          }
        }
      },
      dtype: 'struct'
    }
  }
};

const SELECT_ROWS_RESPONSE_FIXTURE = {
  title: 'title text',
  comment_text: 'text content',
  tags: ['tag1', 'tag2'],
  complex_field: {
    propertyA: 'valueA',
    propertyB: 'valueB'
  },
  complex_list_of_struct: [
    {
      propertyA: 'valueA',
      propertyB: 'valueB'
    },
    {
      propertyA: 'valueC',
      propertyB: 'valueD'
    }
  ],
  __rowid__: 'hNRA5Z_GKkHNiqn0',
  __lilac__: {
    comment_text: {
      pii: {
        emails: [
          {
            [ENTITY_FEATURE_KEY]: {
              start: 1,
              end: 19
            }
          },
          {
            [ENTITY_FEATURE_KEY]: {
              start: 82,
              end: 100
            }
          }
        ]
      }
    },
    complex_field: {
      propertyA: {
        text_statistics: {
          num_characters: 100
        }
      }
    }
  }
};

describe('lilac', () => {
  const schema = deserializeSchema(MANIFEST_SCHEMA_FIXTURE);
  const row = deserializeRow(SELECT_ROWS_RESPONSE_FIXTURE, schema);

  describe('deserializeSchema', () => {
    it('should deserialize a schema', () => {
      expect(schema).toBeDefined();
      expect(schema.fields?.title).toBeDefined();
      expect(schema.fields?.__lilac__).toBeUndefined();
    });

    it('merges signals into the source fields', () => {
      expect(schema.fields?.comment_text).toBeDefined();
      expect(schema.fields?.comment_text.fields?.pii).toBeDefined();
    });

    it('adds paths to all fields', () => {
      expect(schema.fields?.title.path).toEqual(['title']);
      expect(schema.fields?.complex_field.fields?.propertyA.path).toEqual([
        'complex_field',
        'propertyA'
      ]);

      expect(schema.fields?.complex_list_of_struct.repeated_field?.fields?.propertyA.path).toEqual([
        'complex_list_of_struct',
        '*',
        'propertyA'
      ]);

      expect(schema.fields?.comment_text.fields?.pii.path).toEqual([
        '__lilac__',
        'comment_text',
        'pii'
      ]);
    });
  });

  describe('deserializeRow', () => {
    it('should deserialize a row', () => {
      expect(row).toBeDefined();

      expect(value(row.title)).toBeDefined();
      expect(row.__lilac__).toBeUndefined();
      expect(value(row.title)).toEqual('title text');
      expect(value(row.complex_field.propertyA)).toEqual('valueA');
      expect(path(row.complex_field.propertyA)).toEqual(['complex_field', 'propertyA']);
      expect(value(row.complex_list_of_struct[0].propertyA)).toEqual('valueA');
    });

    it('merges signals into the source fields', () => {
      expect(value(row.comment_text.pii.emails[0])).toEqual({
        end: 19,
        start: 1
      });
    });
  });

  describe('listFields', () => {
    it('should return a list of fields', () => {
      const fields = listFields(schema);
      expect(fields).toBeDefined();
      expect(fields[0].dtype).toEqual('string');
      const paths = fields.map((f) => f.path);
      expect(paths).toContainEqual(['title']);
      expect(paths).toContainEqual(['complex_list_of_struct', '*']);
      expect(paths).toContainEqual(['complex_list_of_struct', '*', 'propertyA']);
    });
  });

  describe.only('listValues', () => {
    it('should return a list of values', () => {
      const values = listValues(row);

      expect(values).toBeDefined();
      expect(path(values[0])).toEqual(['title']);
      expect(value(values[0])).toEqual('title text');

      expect(values).not.toContainEqual([]);
      expect(values).not.toContainEqual(null);

      const paths = values.map((f) => path(f));
      expect(paths).toContainEqual(['title']);
      expect(paths).toContainEqual(['complex_list_of_struct', '*']);
      expect(paths).toContainEqual(['complex_list_of_struct', '*', 'propertyA']);
    });
  });

  describe('getField', () => {
    it('should return simple paths', () => {
      const field = getField(schema, ['title']);
      expect(field?.path).toEqual(['title']);
    });
    it('should return a field by path with repeated fields', () => {
      const field = getField(schema, ['complex_list_of_struct', '*', 'propertyA']);
      expect(field?.path).toEqual(['complex_list_of_struct', '*', 'propertyA']);
    });
  });

  describe('getValue', () => {
    it('should return simple paths', () => {
      const value = getValue(row, ['title']);
      expect(value?.path).toEqual(['title']);
      expect(value?.value).toEqual('title text');
    });

    it('should return a value by path with repeated fields', () => {
      const value = getValue(row, ['complex_list_of_struct', '*']);
      expect(value?.path).toEqual(['complex_list_of_struct', '*']);
    });
  });

  describe('getters', () => {
    it('can get path', () => {
      expect(path(row.title)).toEqual(['title']);
    });
    it('can get value', () => {
      expect(value(row.title)).toEqual('title text');
    });
    it('can get field', () => {
      expect(field(row.title, schema)?.path).toEqual(['title']);
    });
    it('can get dtype', () => {
      expect(dtype(row.title, schema)).toEqual('string');
    });
  });
});
