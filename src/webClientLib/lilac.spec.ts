import { describe, expect, it } from 'vitest';
import { Schema } from './fastapi_client';
import { LilacRow, LilacSchema, LilacSelectRowsResponse } from './lilac';

const MANIFEST_SCHEMA: Schema = {
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
  title: 'title text',
  comment_text: 'text content',
  tags: ['tag1', 'tag2'],
  complex_field: {
    propertyA: 'valueA',
    propertyB: 'valueB'
  },
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
    const response = LilacSelectRowsResponse([SELECT_ROWS_RESPONSE_FIXTURE], MANIFEST_SCHEMA);
    expect(response.rows.length).toBe(1);
    expect(response.rows[0].children?.title.value).toEqual('title text');
  });
});

describe('LilacSchema', () => {
  const schema = LilacSchema(MANIFEST_SCHEMA);

  it('has children from fields', () => {
    expect(schema.children?.title).toBeDefined();
    expect(schema.children?.title.children).not.toBeDefined();
    expect(schema.children?.title.dataType).toBe('string');
  });

  it('populates hasChildren', () => {
    expect(schema.children?.title.hasChildren()).toBeFalsy();
    expect(schema.children?.complex_field.hasChildren()).toBeTruthy();
  });

  it('populates annotations', () => {
    expect(schema.children?.comment_text.hasChildren()).toBeTruthy();
    expect(schema.children?.comment_text.children?.pii.children?.emails).toBeDefined();
  });

  it('populates isAnnotation', () => {
    expect(schema.children?.comment_text.children?.pii.isSignalField).toBeTruthy();
    expect(schema.children?.comment_text.isSignalField).toBeFalsy();
  });

  it('handles repeated fields', () => {
    expect(schema.children?.tags.dataType).toBe('string[]');
    expect(schema.children?.tags.path).toEqual(['tags', '*']);
  });
});

describe('LilacRow', () => {
  const response = LilacRow(MANIFEST_SCHEMA, SELECT_ROWS_RESPONSE_FIXTURE);
  it('children has values', () => {
    expect(response.children?.title).toBeDefined();
    expect(response.children?.title?.value).toBe('title text');
    expect(response.children?.title?.hasChildren()).toBeFalsy();

    expect(response.children?.complex_field?.children?.propertyA?.value).toBe('valueA');
    expect(response.children?.complex_field?.children?.propertyB?.value).toBe('valueB');
    expect(response.children?.complex_field?.children?.propertyB?.dataType).toBe('string');
  });

  it('has an id from __rowid__', () => {
    expect(response.id).toBe('hNRA5Z_GKkHNiqn0');
  });

  it('handles repeated field value types', () => {
    expect(response.children?.tags.value).toEqual(['tag1', 'tag2']);
    const t = response.children?.tags;
    if (t?.dataType === 'string[]') {
      t.value;
    }
  });

  it('has annotations values', () => {
    const col = response.children?.comment_text?.children?.pii?.children?.emails;
    expect(col?.path).toEqual(['__lilac__', 'comment_text', 'pii', 'emails', '*', '__entity__']);
    expect(col?.dataType).toEqual('string_span[]');
    expect(col?.value).toEqual([
      {
        start: 1,
        end: 19
      },
      {
        start: 82,
        end: 100
      }
    ]);
    if (col?.dataType === 'string_span') {
      col.value;
    }
  });
});
