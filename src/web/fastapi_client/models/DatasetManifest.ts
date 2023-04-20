/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { EmbeddingIndexerManifest } from './EmbeddingIndexerManifest';
import type { Schema } from './Schema';

/**
 * The manifest for a dataset.
 */
export type DatasetManifest = {
    namespace: string;
    dataset_name: string;
    data_schema: Schema;
    embedding_manifest: EmbeddingIndexerManifest;
    num_items: number;
};

