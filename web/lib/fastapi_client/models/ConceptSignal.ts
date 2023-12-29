/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * Compute scores along a given concept for documents.
 */
export type ConceptSignal = {
    signal_name: 'concept_score';
    output_type?: ('embedding' | 'cluster' | null);
    map_batch_size?: (number | null);
    map_parallelism?: number;
    map_strategy?: 'processes' | 'threads';
    /**
     * The name of the pre-computed embedding.
     */
    embedding: 'cohere' | 'sbert' | 'openai' | 'palm' | 'gte-tiny' | 'gte-small' | 'gte-base' | 'jina-v2-small' | 'jina-v2-base';
    namespace: string;
    concept_name: string;
    version?: (number | null);
    draft?: string;
};

