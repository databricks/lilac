/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LoadDatasetOptions } from '../models/LoadDatasetOptions';
import type { LoadDatasetResponse } from '../models/LoadDatasetResponse';
import type { SourcesList } from '../models/SourcesList';

import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class DataLoadersService {

    /**
     * Get Sources
     * Get the list of available sources.
     * @returns SourcesList Successful Response
     * @throws ApiError
     */
    public static getSources(): CancelablePromise<SourcesList> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/data_loaders/',
        });
    }

    /**
     * Get Source Schema
     * Get the fields for a source.
     * @param sourceName
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getSourceSchema(
        sourceName: string,
    ): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/data_loaders/{source_name}',
            path: {
                'source_name': sourceName,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Load
     * Load a dataset.
     * @param sourceName
     * @param requestBody
     * @returns LoadDatasetResponse Successful Response
     * @throws ApiError
     */
    public static load(
        sourceName: string,
        requestBody: LoadDatasetOptions,
    ): CancelablePromise<LoadDatasetResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/data_loaders/{source_name}/load',
            path: {
                'source_name': sourceName,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }

}
