/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Sensitivity } from './Sensitivity';

/**
 * Compute scores along a given concept for documents.
 */
export type ConceptScoreSignal = {
    signal_name?: 'concept_score';
    split?: 'sentences';
    embedding: 'cohere' | 'sbert';
    namespace: string;
    concept_name: string;
    draft?: string;
    sensitivity?: Sensitivity;
};

