/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * The request for the download dataset endpoint.
 */
export type DownloadOptions = {
    format: 'csv' | 'json' | 'parquet';
    filepath: string;
    jsonl?: (boolean | null);
    columns?: Array<(Array<string> | string)>;
    include_labels?: Array<string>;
    exclude_labels?: Array<string>;
};

