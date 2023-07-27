/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * Compute semantic similarity for a query and a document.
 *
 * This is done by embedding the query with the same embedding as the document and computing a
 * a similarity score between them.
 */
export type SemanticSimilaritySignal = {
    signal_name?: 'semantic_similarity';
    embedding: string;
    query: string;
};

