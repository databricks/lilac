/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ExampleOrigin } from './ExampleOrigin';

/**
 * A single example in a concept used for training a concept model.
 */
export type Example = {
    label: boolean;
    text?: (string | null);
    img?: (Blob | null);
    origin?: (ExampleOrigin | null);
    draft?: (string | null);
    id: string;
};

