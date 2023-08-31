/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class LangsmithService {

    /**
     * Get Datasets
     * List the datasets in LangSmith.
     * @returns string Successful Response
     * @throws ApiError
     */
    public static getDatasets(): CancelablePromise<Array<string>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/langsmith/datasets',
        });
    }

}
