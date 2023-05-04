/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EmbeddingInfo } from '../models/EmbeddingInfo';

import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class EmbeddingsService {

    /**
     * Get Embeddings
     * List the datasets.
     * @returns EmbeddingInfo Successful Response
     * @throws ApiError
     */
    public static getEmbeddings(): CancelablePromise<Array<EmbeddingInfo>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/embeddings/',
        });
    }

}
