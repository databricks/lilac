/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * A keyword search query on a column.
 */
export type KeywordSearch = {
    path: (Array<string> | string);
    query: string;
    type?: 'keyword';
};

