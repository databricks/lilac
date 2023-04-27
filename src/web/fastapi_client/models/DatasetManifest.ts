/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { EmbeddingIndexerManifest } from './EmbeddingIndexerManifest';
import type { EntityIndex } from './EntityIndex';
import type { Schema } from './Schema';

/**
 * The manifest for a dataset.
 */
export type DatasetManifest = {
    namespace: string;
    dataset_name: string;
    data_schema: Schema;
    embedding_manifest: EmbeddingIndexerManifest;
    entity_indexes: Array<EntityIndex>;
    num_items: number;
};

