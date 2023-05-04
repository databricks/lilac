/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Embedding } from './Embedding';

/**
 * Compute scores along a "concept" for documents.
 */
export type ConceptScoreSignal = {
    signal_name?: string;
    embedding?: (string | Embedding);
    namespace: string;
    concept_name: string;
    embedding_name: string;
};

