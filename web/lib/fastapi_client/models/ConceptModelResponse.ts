/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptModelInfo } from './ConceptModelInfo';

/**
 * Response body for the get_concept_model endpoint.
 */
export type ConceptModelResponse = {
    model: ConceptModelInfo;
    model_synced: boolean;
};

