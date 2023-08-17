/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptType } from './ConceptType';

/**
 * Options for creating a concept.
 */
export type CreateConceptOptions = {
    namespace: string;
    name: string;
    type: ConceptType;
    description?: string;
};

