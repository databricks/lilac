/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * Interface for signals to implement. A signal can score documents and a dataset column.
 */
export type Signal = {
    signal_name: string;
    output_type?: ('embedding' | 'cluster' | null);
    map_batch_size?: number;
    map_parallelism?: number;
    map_strategy?: 'processes' | 'threads';
};

