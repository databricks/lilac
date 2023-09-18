/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptACL } from './ConceptACL';
import type { ConceptMetadata_Output } from './ConceptMetadata_Output';
import type { ConceptType } from './ConceptType';

/**
 * Information about a concept.
 */
export type ConceptInfo = {
    namespace: string;
    name: string;
    type: ConceptType;
    metadata: ConceptMetadata_Output;
    drafts: Array<string>;
    acls: ConceptACL;
};

