/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Sensitivity } from './Sensitivity';

/**
 * Compute scores along a given concept for documents.
 */
export type ConceptScoreSignal = {
    signal_name?: 'concept_score';
    embedding: 'cohere' | 'sbert';
    namespace: string;
    concept_name: string;
    draft?: string;
    sensitivity?: Sensitivity;
    num_negative_examples?: number;
};



namespace/dataset_name/select_rows?columns=[{path: 'body', signal_udf: {name: concept_scorer}}])


namespace/dataset_name/select_rows?columns=[{path: 'body', signal_udf: {name: concept_scorer, column_info:{''}}}])
