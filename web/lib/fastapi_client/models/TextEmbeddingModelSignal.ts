/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * An interface for signals that take embeddings and produce items.
 */
export type TextEmbeddingModelSignal = {
    signal_name?: string;
    embedding: 'cohere' | 'sbert' | 'openai' | 'palm';
};

