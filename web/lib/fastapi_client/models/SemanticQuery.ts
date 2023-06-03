/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * A semantic search on a column.
 */
export type SemanticQuery = {
    type?: 'semantic';
    search: string;
    embedding: string;
};

