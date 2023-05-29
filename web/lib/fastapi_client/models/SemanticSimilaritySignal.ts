/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * Compute semantic similarity for a query and a document.
 *
 * <br>This is done by embedding the query with the same embedding as the document and computing a
 * a similarity score between them.
 */
export type SemanticSimilaritySignal = {
    signal_name?: 'semantic_similarity';
    split?: 'sentences' | 'chunk';
    embedding: 'cohere' | 'sbert';
    query: string;
};

