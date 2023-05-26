/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptDatasetOptions } from './ConceptDatasetOptions';
import type { SignalInputType } from './SignalInputType';

/**
 * Options for creating a concept.
 */
export type CreateConceptOptions = {
    namespace: string;
    name: string;
    type: SignalInputType;
    dataset?: ConceptDatasetOptions;
};

