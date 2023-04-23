/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Signal } from './Signal';

/**
 * The rest API for computing a UDF with a signal.
 */
export type SignalUDFOptions = {
    signal: Signal;
    path: Array<(string | number)>;
    alias: string;
};

