/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * A filter on a column.
 */
export type UnaryFilter = {
    path: (Array<string> | string);
    op: 'exists';
    value?: null;
};

