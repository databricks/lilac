/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * Compute semantic similarity for between a document.
 *
 * <br>This is done by embedding the query with the same embedding as the document and computing a
 * a similarity score between them.
 */
export type SemanticSearchSignal = {
    signal_name?: 'semantic_search';
    split?: 'sentences';
    embedding: 'cohere';
    query: string;
};

