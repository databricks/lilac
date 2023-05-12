/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * Compute scores along a "concept" for documents.
 */
export type ConceptScoreSignal = {
    signal_name?: string;
    namespace: string;
    concept_name: string;
    embedding_name: string;
};

