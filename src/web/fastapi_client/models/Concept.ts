/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Example } from './Example';

/**
 * A concept is a collection of examples.
 */
export type Concept = {
    namespace?: string;
    concept_name: string;
    type: ('text' | 'img');
    data: Record<string, Example>;
    version?: number;
};

