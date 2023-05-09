/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * The request for the compute signal endpoint.
 */
export type ComputeSignalOptions = {
    signal_name: string;
    signal_args?: any;
    leaf_path: Array<(number | string)>;
};

