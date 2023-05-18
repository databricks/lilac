/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptModel } from './ConceptModel';

/**
 * Response body for the get_concept_model endpoint.
 */
export type ConceptModelResponse = {
    model: ConceptModel;
    model_synced: boolean;
};

