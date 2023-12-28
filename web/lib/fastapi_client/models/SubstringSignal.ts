/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * Find a substring in a document.
 */
export type SubstringSignal = {
    signal_name: 'substring_search';
    output_type?: ('embedding' | 'cluster' | null);
    map_batch_size?: number;
    map_parallelism?: number;
    map_strategy?: 'processes' | 'threads';
    query: string;
};

