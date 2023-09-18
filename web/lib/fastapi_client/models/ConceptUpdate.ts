/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Example } from './Example';
import type { ExampleIn } from './ExampleIn';

/**
 * An update to a concept.
 */
export type ConceptUpdate = {
    insert?: (Array<ExampleIn> | null);
    update?: (Array<Example> | null);
    remove?: (Array<string> | null);
};

