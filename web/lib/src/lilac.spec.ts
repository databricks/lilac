import {assertType, describe, expect, it} from 'vitest';
import type {Schema} from '../fastapi_client';
import {
  L,
  childFields,
  deserializeRow,
  deserializeSchema,
  getField,
  getValueNodes,
  isSignalField,
  listFieldParents,
  listValueNodes
} from './lilac';
import {VALUE_KEY, type FieldValue} from './schema';

const MANIFEST_SCHEMA_FIXTURE: Schema = {
  fields: {
    title: {
      dtype: 'string'
    },
    comment_text: {
      dtype: 'string',
      fields: {
        pii: {
          fields: {
            emails: {
              repeated_field: {
                fields: {},
                dtype: 'string_span'
              }
            }
          },
          signal: {signal_name: 'pii'}
        }
      }
    },
    complex_field: {
      fields: {
        propertyA: {
          dtype: 'string',
          fields: {
            text_statistics: {
              fields: {
                num_characters: {
                  dtype: 'int32'
                }
              },
              signal: {signal_name: 'text_statistics'}
            }
          }
        },
        propertyB: {
          dtype: 'string'
        }
      }
    },
    tags: {
      repeated_field: {
        dtype: 'string'
      }
    },
    complex_list_of_struct: {
      repeated_field: {
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
    nested_list_of_list: {
      repeated_field: {
        repeated_field: {
          dtype: 'string'
        }
      }
    },
    __rowid__: {
      dtype: 'string'
    }
  }
};

const SELECT_ROWS_RESPONSE_FIXTURE: FieldValue = {
  title: lilacItem('title text'),
  comment_text: lilacItem('text content', {
    pii: {
      emails: [
        {
          [VALUE_KEY]: {
            start: 1,
            end: 19
          }
        },
        {
          [VALUE_KEY]: {
            start: 82,
            end: 100
          }
        }
      ]
    }
  }),
  tags: [lilacItem('tag1'), lilacItem('tag2')],
  complex_field: {
    propertyA: lilacItem('valueA', {
      propertyA: {
        text_statistics: {
          num_characters: lilacItem(100)
        }
      }
    }),
    propertyB: lilacItem('valueB')
  },
  complex_list_of_struct: [
    {
      propertyA: lilacItem('valueA'),
      propertyB: lilacItem('valueB')
    },
    {
      propertyA: lilacItem('valueC'),
      propertyB: lilacItem('valueD')
    }
  ],
  nested_list_of_list: [
    [lilacItem('a'), lilacItem('b')],
    [lilacItem('c'), lilacItem('d')]
  ],
  __rowid__: 'hNRA5Z_GKkHNiqn0'
};

function lilacItem(value: FieldValue, fields: {[fieldName: string]: FieldValue} = {}) {
  return {
    [VALUE_KEY]: value,
    ...fields
  };
}

describe('lilac', () => {
  const schema = deserializeSchema(MANIFEST_SCHEMA_FIXTURE);
  const row = deserializeRow(SELECT_ROWS_RESPONSE_FIXTURE, schema);

  describe('deserializeSchema', () => {
    it('should deserialize a schema', () => {
      expect(schema).toBeDefined();
      expect(schema.fields?.title).toBeDefined();
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

      expect(schema.fields?.comment_text.fields?.pii.path).toEqual(['comment_text', 'pii']);
    });
  });

  describe('deserializeRow', () => {
    it('should deserialize a row', () => {
      expect(row).toBeDefined();

      expect(L.value(row.title)).toBeDefined();
      expect(L.value(row.title)).toEqual('title text');
      expect(L.value(row.complex_field.propertyA)).toEqual('valueA');
      expect(L.path(row.complex_field.propertyA)).toEqual(['complex_field', 'propertyA']);
      expect(L.value(row.complex_list_of_struct[0].propertyA)).toEqual('valueA');
    });

    it('merges signals into the source fields', () => {
      expect(L.value(row.comment_text.pii.emails[0])).toEqual({
        end: 19,
        start: 1
      });
    });
  });

  describe('childFields', () => {
    it('should return a list of fields', () => {
      const fields = childFields(schema);
      expect(fields).toBeDefined();
      expect(fields[1].dtype).toEqual('string');
      const paths = fields.map(f => f.path);
      expect(paths).toContainEqual(['title']);
      expect(paths).toContainEqual(['complex_list_of_struct', '*']);
      expect(paths).toContainEqual(['complex_list_of_struct', '*', 'propertyA']);
    });
    it('should not return root field', () => {
      const fields = childFields(schema);
      expect(fields).not.toContainEqual([]);
      expect(fields).not.toContainEqual(null);
    });
  });

  describe('listFieldParents', () => {
    it('lists the parents of a field', () => {
      const parents = listFieldParents(
        schema.fields!.complex_field.fields!.propertyA.fields!.text_statistics,
        schema
      );
      expect(parents).toBeDefined();
      expect(parents).toHaveLength(2);
      expect(parents[0]).toEqual(schema.fields!.complex_field);
      expect(parents[1]).toEqual(schema.fields!.complex_field.fields!.propertyA);
    });
  });

  describe('listValues', () => {
    it('should return a list of values', () => {
      const values = listValueNodes(row);
      expect(values).toBeDefined();
      expect(L.path(values[0])).toEqual(['title']);
      expect(L.value(values[0])).toEqual('title text');

      expect(values).not.toContainEqual([]);
      expect(values).not.toContainEqual(null);

      const paths = values.map(f => L.path(f));
      expect(paths).toContainEqual(['title']);
      expect(paths).toContainEqual(['complex_list_of_struct', '0']);
      expect(paths).toContainEqual(['complex_list_of_struct', '0', 'propertyA']);
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

  describe('getValueNodes', () => {
    it('should get all values in repeated fields', () => {
      const values = getValueNodes(row, ['comment_text', 'pii', 'emails', '*']);
      expect(L.value(values[0])).toEqual({
        end: 19,
        start: 1
      });
      expect(L.value(values[1])).toEqual({
        end: 100,
        start: 82
      });
      expect(values).toHaveLength(2);
    });
  });

  describe('getters', () => {
    it('can get path', () => {
      expect(L.path(row.title)).toEqual(['title']);
      expect(L.path(row.non_existing_field)).not.toBeDefined();
    });
    it('can get value', () => {
      expect(L.value(row.title)).toEqual('title text');
    });
    it('can get field', () => {
      expect(L.field(row.title)?.path).toEqual(['title']);
    });
    it('can get dtype', () => {
      expect(L.dtype(row.title)).toEqual('string');
    });

    it('cam get typed values as strings', () => {
      const t = L.dtype(row.title);
      if (t === 'string') {
        const val = L.value(row.title, t);
        assertType<string>(val!);
      } else {
        // Woops, this should never happen
        expect(0).toEqual(1);
      }
    });

    it('cam get typed values as string_span', () => {
      const t = L.dtype(row.comment_text.pii.emails[0]);
      if (t === 'string_span') {
        const val = L.value(row.title, t);
        assertType<{start: number; end: number}>(val!);
      } else {
        // Woops, this should never happen
        expect(0).toEqual(1);
      }
    });
  });

  describe('utilities', () => {
    it('isSignalField', () => {
      expect(isSignalField(schema.fields!.comment_text!, schema)).toEqual(false);
      expect(isSignalField(schema.fields!.comment_text.fields!.pii, schema)).toEqual(true);
    });
  });

  describe('nested lists', () => {
    it('can get values', () => {
      expect(L.path(row.nested_list_of_list[0][0])).toEqual(['nested_list_of_list', '0', '0']);
      expect(L.dtype(row.nested_list_of_list[0][0])).toEqual('string');
    });
  });
});
