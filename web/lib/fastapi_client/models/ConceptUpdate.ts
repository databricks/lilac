/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Example } from './Example';
import type { ExampleIn } from './ExampleIn';
import type { ExampleRemove } from './ExampleRemove';

/**
 * An update to a concept.
 */
export type ConceptUpdate = {
    insert?: Array<ExampleIn>;
    update?: Array<Example>;
    remove?: Array<ExampleRemove>;
};

