/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SignalComputeOptions } from '../models/SignalComputeOptions';
import type { SignalComputeResponse } from '../models/SignalComputeResponse';
import type { SignalInfo } from '../models/SignalInfo';

import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class SignalsService {

    /**
     * Get Signals
     * List the signals.
     * @returns SignalInfo Successful Response
     * @throws ApiError
     */
    public static getSignals(): CancelablePromise<Array<SignalInfo>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/signals/',
        });
    }

    /**
     * Get Embeddings
     * List the embeddings.
     * @returns SignalInfo Successful Response
     * @throws ApiError
     */
    public static getEmbeddings(): CancelablePromise<Array<SignalInfo>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/signals/embeddings',
        });
    }

    /**
     * Compute
     * Compute a signal over a set of inputs.
     * @param requestBody
     * @returns SignalComputeResponse Successful Response
     * @throws ApiError
     */
    public static compute(
        requestBody: SignalComputeOptions,
    ): CancelablePromise<SignalComputeResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/signals/compute',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }

}
