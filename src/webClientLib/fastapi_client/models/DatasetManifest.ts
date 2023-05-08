/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Schema } from './Schema';

/**
 * The manifest for a dataset.
 */
export type DatasetManifest = {
    namespace: string;
    dataset_name: string;
    data_schema: Schema;
    num_items: number;
};

