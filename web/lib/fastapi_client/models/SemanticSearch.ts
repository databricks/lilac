/* generated using openapi-typescript-codegen -- do no edit */
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
    type: 'semantic';
    /**
     * The input type of the query, used for the query embedding.
     */
    query_type?: 'question' | 'document';
};

