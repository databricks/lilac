/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ComputeSignalOptions } from '../models/ComputeSignalOptions';
import type { ComputeSignalResponse } from '../models/ComputeSignalResponse';
import type { DatasetInfo } from '../models/DatasetInfo';
import type { GetStatsOptions } from '../models/GetStatsOptions';
import type { SelectGroupsOptions } from '../models/SelectGroupsOptions';
import type { SelectRowsOptions } from '../models/SelectRowsOptions';
import type { StatsResult } from '../models/StatsResult';
import type { WebManifest } from '../models/WebManifest';

import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class DatasetsService {

    /**
     * Get Datasets
     * List the datasets.
     * @returns DatasetInfo Successful Response
     * @throws ApiError
     */
    public static getDatasets(): CancelablePromise<Array<DatasetInfo>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/datasets/',
        });
    }

    /**
     * Get Manifest
     * Get the web manifest for the dataset.
     * @param namespace
     * @param datasetName
     * @returns WebManifest Successful Response
     * @throws ApiError
     */
    public static getManifest(
        namespace: string,
        datasetName: string,
    ): CancelablePromise<WebManifest> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/datasets/{namespace}/{dataset_name}',
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
     * Compute Signal Column
     * Compute a signal for a dataset.
     * @param namespace
     * @param datasetName
     * @param requestBody
     * @returns ComputeSignalResponse Successful Response
     * @throws ApiError
     */
    public static computeSignalColumn(
        namespace: string,
        datasetName: string,
        requestBody: ComputeSignalOptions,
    ): CancelablePromise<ComputeSignalResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/datasets/{namespace}/{dataset_name}/compute_signal_column',
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
     * Get Stats
     * Get the stats for the dataset.
     * @param namespace
     * @param datasetName
     * @param requestBody
     * @returns StatsResult Successful Response
     * @throws ApiError
     */
    public static getStats(
        namespace: string,
        datasetName: string,
        requestBody: GetStatsOptions,
    ): CancelablePromise<StatsResult> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/datasets/{namespace}/{dataset_name}/stats',
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
     * @param requestBody
     * @returns any Successful Response
     * @throws ApiError
     */
    public static selectRows(
        namespace: string,
        datasetName: string,
        requestBody: SelectRowsOptions,
    ): CancelablePromise<Array<any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/datasets/{namespace}/{dataset_name}/select_rows',
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
     * Select Groups
     * Select groups from the dataset database.
     * @param namespace
     * @param datasetName
     * @param requestBody
     * @returns any Successful Response
     * @throws ApiError
     */
    public static selectGroups(
        namespace: string,
        datasetName: string,
        requestBody: SelectGroupsOptions,
    ): CancelablePromise<Array<Array<any>>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/datasets/{namespace}/{dataset_name}/select_groups',
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
     * Get Media
     * Get the media for the dataset.
     * @param namespace
     * @param datasetName
     * @param itemId
     * @param leafPath
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getMedia(
        namespace: string,
        datasetName: string,
        itemId: string,
        leafPath: string,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/datasets/{namespace}/{dataset_name}/media',
            path: {
                'namespace': namespace,
                'dataset_name': datasetName,
            },
            query: {
                'item_id': itemId,
                'leaf_path': leafPath,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }

}
