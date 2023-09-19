/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * A semantic search on a column.
 */
export type SemanticSearch = {
    path: (Array<string> | string);
    query: string;
    embedding: string;
    type?: 'semantic';
};

