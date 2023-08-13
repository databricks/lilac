/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptACL } from './ConceptACL';
import type { ConceptType } from './ConceptType';

/**
 * Information about a concept.
 */
export type ConceptInfo = {
    namespace: string;
    name: string;
    description?: string;
    type: ConceptType;
    drafts: Array<('main' | string)>;
    tags?: Array<string>;
    acls: ConceptACL;
};

