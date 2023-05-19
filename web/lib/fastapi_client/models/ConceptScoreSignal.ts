/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * Compute scores along a given concept for documents.
 */
export type ConceptScoreSignal = {
    signal_name?: 'concept_score';
    split?: 'sentences';
    embedding: 'cohere';
    namespace: string;
    concept_name: string;
};

