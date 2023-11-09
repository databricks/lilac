/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * An interface for signals that compute embeddings for text.
 */
export type TextEmbeddingSignal = {
    signal_name: string;
    /**
     * The input type to the embedding.
     */
    embed_input_type?: 'question' | 'document';
};

