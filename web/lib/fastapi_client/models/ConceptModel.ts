/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptThreshold } from './ConceptThreshold';

/**
 * A concept model.
 */
export type ConceptModel = {
    namespace: string;
    concept_name: string;
    embedding_name: string;
    version?: number;
    thresholds?: Array<ConceptThreshold>;
};

