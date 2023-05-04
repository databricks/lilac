/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { EmbeddingIndexInfo } from './EmbeddingIndexInfo';

/**
 * The manifest of an embedding indexer.
 */
export type EmbeddingIndexerManifest = {
    indexes: Array<EmbeddingIndexInfo>;
};

