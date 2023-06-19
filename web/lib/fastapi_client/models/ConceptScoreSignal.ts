/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * Compute scores along a given concept for documents.
 */
export type ConceptScoreSignal = {
    signal_name?: 'concept_score';
    embedding: 'cohere' | 'sbert';
    namespace: string;
    concept_name: string;
    draft?: string;
    num_negative_examples?: number;
};

