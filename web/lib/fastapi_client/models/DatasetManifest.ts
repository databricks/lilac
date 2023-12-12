/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { DatasetFormat } from './DatasetFormat';
import type { Schema } from './Schema';
import type { Source } from './Source';

/**
 * The manifest for a dataset.
 */
export type DatasetManifest = {
    namespace: string;
    dataset_name: string;
    data_schema: Schema;
    source: Source;
    num_items: number;
    dataset_format?: (DatasetFormat | null);
};

