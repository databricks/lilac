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
     * The input type to the embedding. Use `document` to embed documents, and `query` to embed a query from a user.
     */
    embed_input_type?: 'query' | 'document';
};

