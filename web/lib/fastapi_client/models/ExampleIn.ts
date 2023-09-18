/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ExampleOrigin } from './ExampleOrigin';

/**
 * An example in a concept without the id (used for adding new examples).
 */
export type ExampleIn = {
    label: boolean;
    text?: (string | null);
    img?: (Blob | null);
    origin?: (ExampleOrigin | null);
    draft?: (string | null);
};

