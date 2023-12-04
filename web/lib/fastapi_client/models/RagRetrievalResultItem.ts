/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { RagRetrievalSpan } from './RagRetrievalSpan';

/**
 * The result of the RAG retrieval model.
 */
export type RagRetrievalResultItem = {
    rowid: string;
    text: string;
    metadata: Record<string, any>;
    score: number;
    match_spans: Array<RagRetrievalSpan>;
};

