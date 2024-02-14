/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * Compute scores along a given concept for documents.
 */
export type ConceptSignal = {
    signal_name: 'concept_score';
    /**
     * The name of the pre-computed embedding.
     */
    embedding: 'cohere' | 'sbert' | 'openai' | 'gte-tiny' | 'gte-small' | 'gte-base' | 'jina-v2-small' | 'jina-v2-base' | 'bge-m3' | 'nomic-embed-1.5-768' | 'nomic-embed-1.5-256';
    namespace: string;
    concept_name: string;
    version?: (number | null);
    draft?: string;
};

