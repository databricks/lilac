/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Embedding } from './Embedding';

/**
 * The request for the compute embedding index endpoint.
 */
export type ComputeEmbeddingIndexOptions = {
    embedding: Embedding;
    leaf_path: Array<(number | string)>;
};

