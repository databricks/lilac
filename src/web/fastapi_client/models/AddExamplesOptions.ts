/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { AddExample } from './AddExample';

/**
 * The request for the add examples endpoint.
 */
export type AddExamplesOptions = {
    username: string;
    name: string;
    examples: Array<AddExample>;
};

