/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ComputeEmbeddingIndexOptions } from '../models/ComputeEmbeddingIndexOptions';
import type { ComputeSignalOptions } from '../models/ComputeSignalOptions';
import type { SortOrder } from '../models/SortOrder';

import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class DatasetService {

    /**
     * Manifest
     * Get the web manifest for the dataset.
     * @param namespace
     * @param datasetName
     * @returns any Successful Response
     * @throws ApiError
     */
    public static manifest(
        namespace: string,
        datasetName: string,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/dataset/{namespace}/{dataset_name}/manifest',
            path: {
                'namespace': namespace,
                'dataset_name': datasetName,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Compute Embedding Index
     * Compute a signal for a dataset.
     * @param namespace
     * @param datasetName
     * @param requestBody
     * @returns any Successful Response
     * @throws ApiError
     */
    public static computeEmbeddingIndex(
        namespace: string,
        datasetName: string,
        requestBody: ComputeEmbeddingIndexOptions,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/dataset/{namespace}/{dataset_name}/compute_embedding_index',
            path: {
                'namespace': namespace,
                'dataset_name': datasetName,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Compute Signal Column
     * Compute a signal for a dataset.
     * @param namespace
     * @param datasetName
     * @param requestBody
     * @returns any Successful Response
     * @throws ApiError
     */
    public static computeSignalColumn(
        namespace: string,
        datasetName: string,
        requestBody: ComputeSignalOptions,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/dataset/{namespace}/{dataset_name}/compute_signal_column',
            path: {
                'namespace': namespace,
                'dataset_name': datasetName,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Select Rows
     * Select rows from the dataset database.
     * @param namespace
     * @param datasetName
     * @param columns
     * @param filters
     * @param sortBy
     * @param sortOrder
     * @param limit
     * @returns any Successful Response
     * @throws ApiError
     */
    public static selectRows(
        namespace: string,
        datasetName: string,
        columns?: string,
        filters?: string,
        sortBy?: string,
        sortOrder?: SortOrder,
        limit?: number,
    ): CancelablePromise<Array<any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/dataset/{namespace}/{dataset_name}/select_rows',
            path: {
                'namespace': namespace,
                'dataset_name': datasetName,
            },
            query: {
                'columns': columns,
                'filters': filters,
                'sort_by': sortBy,
                'sort_order': sortOrder,
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }

}
