/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptMetadata_Input } from './ConceptMetadata_Input';
import type { ConceptType } from './ConceptType';

/**
 * Options for creating a concept.
 */
export type CreateConceptOptions = {
    namespace: string;
    name: string;
    type: ConceptType;
    metadata?: (ConceptMetadata_Input | null);
};

