/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * A filter on a column.
 */
export type UnaryFilter = {
    path: (Array<string> | string);
    op: 'exists' | 'not_exists';
    value?: null;
};

