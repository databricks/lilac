/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * A filter on a column.
 */
export type BinaryFilter = {
    path: (Array<string> | string);
    op: 'equals' | 'not_equal' | 'greater' | 'greater_equal' | 'less' | 'less_equal';
    value: (number | boolean | string | Blob);
};

