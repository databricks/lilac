/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptMetadata_Output } from './ConceptMetadata_Output';
import type { ConceptType } from './ConceptType';
import type { Example_Output } from './Example_Output';

/**
 * A concept is a collection of examples.
 */
export type Concept = {
    namespace: string;
    concept_name: string;
    type: ConceptType;
    data: Record<string, Example_Output>;
    version: number;
    metadata: (ConceptMetadata_Output | null);
};

