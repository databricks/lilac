/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Signal } from './Signal';

/**
 * The request for the standalone compute signal endpoint.
 */
export type SignalComputeOptions = {
    signal: Signal;
    inputs: Array<string>;
};

