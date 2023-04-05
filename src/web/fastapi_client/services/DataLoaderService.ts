/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LoadDatasetOptions } from '../models/LoadDatasetOptions';
import type { LoadDatasetShardOptions } from '../models/LoadDatasetShardOptions';
import type { SourceShardOut } from '../models/SourceShardOut';
import type { SourcesList } from '../models/SourcesList';

import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class DataLoaderService {

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
    ): CancelablePromise<any> {
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
     * @param requestBody
     * @returns any Successful Response
     * @throws ApiError
     */
    public static load(
        requestBody: LoadDatasetOptions,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/data_loaders/load',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Load Shard
     * Process an individual source shard. Each shard is processed in a parallel POST request.
     * @param requestBody
     * @returns SourceShardOut Successful Response
     * @throws ApiError
     */
    public static loadShard(
        requestBody: LoadDatasetShardOptions,
    ): CancelablePromise<SourceShardOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/data_loaders/load_shard',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }

}
