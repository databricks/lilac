/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * A filter on a column.
 */
export type Filter = {
    path: Array<string>;
    op: ('equals' | 'not_equal' | 'greater' | 'greater_equal' | 'less' | 'less_equal' | 'length_longer' | 'length_shorter' | 'regex_matches' | 'not_regex_matches' | 'exists' | 'not_exists' | 'in');
    value?: (number | boolean | string | Blob | Array<string> | null);
};

