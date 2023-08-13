/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptType } from './ConceptType';
import type { Example } from './Example';

/**
 * A concept is a collection of examples.
 */
export type Concept = {
    namespace: string;
    concept_name: string;
    type: ConceptType;
    data: Record<string, Example>;
    version?: number;
    tags?: Array<string>;
    description?: string;
};

