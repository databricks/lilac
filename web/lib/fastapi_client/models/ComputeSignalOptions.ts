/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Signal } from './Signal';

/**
 * The request for the compute signal endpoint.
 */
export type ComputeSignalOptions = {
    signal: Signal;
    leaf_path: (Array<string> | string);
};

