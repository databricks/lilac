/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ExampleOrigin } from './ExampleOrigin';

/**
 * A single example in a concept used for training a concept model.
 */
export type Example = {
    label: boolean;
    text?: string;
    img?: Blob;
    origin?: ExampleOrigin;
    draft?: ('main' | string);
    id: string;
};

