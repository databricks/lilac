/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptDatasetInfo } from './ConceptDatasetInfo';
import type { SignalInputType } from './SignalInputType';

/**
 * Options for creating a concept.
 */
export type CreateConceptOptions = {
    namespace: string;
    name: string;
    type: SignalInputType;
    dataset?: ConceptDatasetInfo;
};

