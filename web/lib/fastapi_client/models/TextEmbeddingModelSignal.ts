/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * An interface for signals that take embeddings and produce items.
 */
export type TextEmbeddingModelSignal = {
    signal_name?: string;
    split?: 'sentences';
    embedding: 'cohere' | 'sbert';
};

