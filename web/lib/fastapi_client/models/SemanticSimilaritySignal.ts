/* generated using openapi-typescript-codegen -- do no edit */
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
    signal_name: 'semantic_similarity';
    /**
     * Accelerate computation on Lilac Garden
     */
    remote?: boolean;
    /**
     * The name of the pre-computed embedding.
     */
    embedding: 'cohere' | 'sbert' | 'openai' | 'palm' | 'gte-tiny' | 'gte-small' | 'gte-base' | 'jina-v2-small' | 'jina-v2-base';
    query: string;
    /**
     * The input type of the query, used for the query embedding.
     */
    query_type?: 'question' | 'document';
};

