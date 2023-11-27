/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * A filter on a column.
 */
export type StringFilter = {
    path: (Array<string> | string);
    op: 'length_longer' | 'length_shorter' | 'regex_matches' | 'not_regex_matches';
    value: string;
};

