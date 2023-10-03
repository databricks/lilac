/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class RagService {

    /**
     * Generate Completion
     * Generate the completion for a prompt.
     * @param prompt
     * @returns string Successful Response
     * @throws ApiError
     */
    public static generateCompletion(
        prompt: string,
    ): CancelablePromise<string> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/rag/generate_completion',
            query: {
                'prompt': prompt,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }

}
