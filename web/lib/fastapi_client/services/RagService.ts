/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RagGenerationOptions } from '../models/RagGenerationOptions';
import type { RagGenerationResult } from '../models/RagGenerationResult';
import type { RagRetrievalOptions } from '../models/RagRetrievalOptions';
import type { RagRetrievalResultItem } from '../models/RagRetrievalResultItem';

import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class RagService {

    /**
     * Retrieval
     * Get the retrieval results for a prompt.
     * @param requestBody
     * @returns RagRetrievalResultItem Successful Response
     * @throws ApiError
     */
    public static retrieval(
        requestBody: RagRetrievalOptions,
    ): CancelablePromise<Array<RagRetrievalResultItem>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/rag/retrieval',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Generate
     * Get the retrieval results for a prompt.
     * @param requestBody
     * @returns RagGenerationResult Successful Response
     * @throws ApiError
     */
    public static generate(
        requestBody: RagGenerationOptions,
    ): CancelablePromise<RagGenerationResult> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/rag/generate',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }

}
