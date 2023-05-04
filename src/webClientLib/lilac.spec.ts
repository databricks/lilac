import { describe, expect, it } from 'vitest';
import { Schema } from './fastapi_client';
import { LilacRow, LilacSchema, LilacSelectRowsResponse } from './lilac';

const MANIFEST_SCHEMA: Schema = {
  fields: {
    id: {
      dtype: 'string'
    },
    comment_text: {
      dtype: 'string'
    },
    complex_field: {
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
    label: {
      dtype: 'string'
    },
    __hfsplit__: {
      dtype: 'string'
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
                    fields: {
                      __entity__: {
                        dtype: 'string_span',
                        derived_from: ['comment_text']
                      }
                    },
                    dtype: 'struct',
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
        }
      },
      dtype: 'struct'
    }
  }
};

const SELECT_ROWS_RESPONSE_FIXTURE = {
  id: '1252339afcb59add',
  comment_text: 'text content',
  label: 'non',
  tags: ['tag1', 'tag2'],
  complex_field: {
    propertyA: 'valueA',
    propertyB: 'valueB'
  },
  __hfsplit__: 'validation',
  __rowid__: 'hNRA5Z_GKkHNiqn0',
  __lilac__: {
    comment_text: {
      pii: {
        emails: [
          {
            __entity__: {
              start: 1,
              end: 19
            }
          },
          {
            __entity__: {
              start: 82,
              end: 100
            }
          }
        ]
      }
    }
  }
};

describe('LilacSelectRowsResponse', () => {
  it('gets created from responses', () => {
    const response = new LilacSelectRowsResponse([SELECT_ROWS_RESPONSE_FIXTURE], MANIFEST_SCHEMA);
    expect(response.rows.length).toBe(1);
    expect(response.rows[0].children?.id.value).toEqual('1252339afcb59add');
  });
});

describe('LilacSchema', () => {
  const schema = new LilacSchema(MANIFEST_SCHEMA);

  it('has children from fields', () => {
    expect(schema.children?.id).toBeDefined();
    expect(schema.children?.id.children).not.toBeDefined();
    expect(schema.children?.id.dataType).toBe('string');
  });
});

describe('LilacRow', () => {
  it('children has values', () => {
    const response = new LilacRow(MANIFEST_SCHEMA, SELECT_ROWS_RESPONSE_FIXTURE);
    expect(response.children?.id).toBeDefined();
    expect(response.children?.id?.value).toBe('1252339afcb59add');
    expect(response.children?.id?.hasChildren).toBeFalsy();

    expect(response.children?.complex_field?.children?.propertyA?.value).toBe('valueA');
    expect(response.children?.complex_field?.children?.propertyB?.value).toBe('valueB');
    expect(response.children?.complex_field?.children?.propertyB?.dataType).toBe('string');
  });
});
