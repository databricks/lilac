/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Embedding } from './Embedding';

/**
 * The information about an embedding index.
 */
export type EmbeddingIndexInfo = {
    column: Array<(string | number)>;
    embedding: Embedding;
};

