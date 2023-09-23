/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { DataType } from './DataType';

/**
 * Holds information for a field in the schema.
 */
export type Field = {
    repeated_field?: (Field | null);
    fields?: (Record<string, Field> | null);
    dtype?: (DataType | null);
    signal?: (Record<string, any> | null);
    label?: (string | null);
    bins?: (Array<any[]> | null);
    categorical?: (boolean | null);
};

