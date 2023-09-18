/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Example_Input } from './Example_Input';
import type { ExampleIn } from './ExampleIn';

/**
 * An update to a concept.
 */
export type ConceptUpdate = {
    insert?: (Array<ExampleIn> | null);
    update?: (Array<Example_Input> | null);
    remove?: (Array<string> | null);
};

