/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Filter } from './Filter';
import type { lilac__data__dataset__Column } from './lilac__data__dataset__Column';

/**
 * The config for the rag retrieval.
 */
export type RagRetrievalOptions = {
    dataset_namespace: string;
    dataset_name: string;
    embedding: string;
    query: string;
    path: (Array<string> | string);
    metadata_columns?: Array<(lilac__data__dataset__Column | Array<string> | string)>;
    filters?: Array<Filter>;
    chunk_window?: number;
    top_k?: number;
    similarity_threshold?: number;
};

