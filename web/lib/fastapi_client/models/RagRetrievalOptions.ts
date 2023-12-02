/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { BinaryFilter } from './BinaryFilter';
import type { Column } from './Column';
import type { ListFilter } from './ListFilter';
import type { StringFilter } from './StringFilter';
import type { UnaryFilter } from './UnaryFilter';

/**
 * The config for the rag retrieval.
 */
export type RagRetrievalOptions = {
    dataset_namespace: string;
    dataset_name: string;
    embedding: string;
    query: string;
    path: (Array<string> | string);
    metadata_columns?: Array<(Column | Array<string> | string)>;
    filters?: Array<(BinaryFilter | StringFilter | UnaryFilter | ListFilter)>;
    chunk_window?: number;
    top_k?: number;
    similarity_threshold?: number;
};

