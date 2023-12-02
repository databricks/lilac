/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { RagRetrievalResultItem } from './RagRetrievalResultItem';

/**
 * The config for the rag generation.
 */
export type RagGenerationOptions = {
    query: string;
    retrieval_results: Array<RagRetrievalResultItem>;
    prompt_template: string;
};

