/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * A filter on a column.
 */
export type BinaryFilter = {
    path: (Array<string> | string);
    op: 'equals' | 'not_equal' | 'greater' | 'greater_equal' | 'less' | 'less_equal';
    value: (boolean | number | string | Blob);
};

