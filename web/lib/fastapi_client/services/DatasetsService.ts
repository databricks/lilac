/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AddLabelsOptions } from '../models/AddLabelsOptions';
import type { ComputeSignalOptions } from '../models/ComputeSignalOptions';
import type { ComputeSignalResponse } from '../models/ComputeSignalResponse';
import type { DatasetInfo } from '../models/DatasetInfo';
import type { DatasetSettings } from '../models/DatasetSettings';
import type { DeleteSignalOptions } from '../models/DeleteSignalOptions';
import type { DeleteSignalResponse } from '../models/DeleteSignalResponse';
import type { ExportOptions } from '../models/ExportOptions';
import type { GetStatsOptions } from '../models/GetStatsOptions';
import type { RemoveLabelsOptions } from '../models/RemoveLabelsOptions';
import type { SelectGroupsOptions } from '../models/SelectGroupsOptions';
import type { SelectGroupsResult } from '../models/SelectGroupsResult';
import type { SelectRowsOptions } from '../models/SelectRowsOptions';
import type { SelectRowsResponse } from '../models/SelectRowsResponse';
import type { SelectRowsSchemaOptions } from '../models/SelectRowsSchemaOptions';
import type { SelectRowsSchemaResult } from '../models/SelectRowsSchemaResult';
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
     * Delete Dataset
     * Delete the dataset.
     * @param namespace
     * @param datasetName
     * @returns any Successful Response
     * @throws ApiError
     */
    public static deleteDataset(
        namespace: string,
        datasetName: string,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'DELETE',
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
     * Compute Signal
     * Compute a signal for a dataset.
     * @param namespace
     * @param datasetName
     * @param requestBody
     * @returns ComputeSignalResponse Successful Response
     * @throws ApiError
     */
    public static computeSignal(
        namespace: string,
        datasetName: string,
        requestBody: ComputeSignalOptions,
    ): CancelablePromise<ComputeSignalResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/datasets/{namespace}/{dataset_name}/compute_signal',
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
     * Delete Signal
     * Delete a signal from a dataset.
     * @param namespace
     * @param datasetName
     * @param requestBody
     * @returns DeleteSignalResponse Successful Response
     * @throws ApiError
     */
    public static deleteSignal(
        namespace: string,
        datasetName: string,
        requestBody: DeleteSignalOptions,
    ): CancelablePromise<DeleteSignalResponse> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/datasets/{namespace}/{dataset_name}/delete_signal',
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
     * @returns SelectRowsResponse Successful Response
     * @throws ApiError
     */
    public static selectRows(
        namespace: string,
        datasetName: string,
        requestBody: SelectRowsOptions,
    ): CancelablePromise<SelectRowsResponse> {
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
     * Select Rows Schema
     * Select rows from the dataset database.
     * @param namespace
     * @param datasetName
     * @param requestBody
     * @returns SelectRowsSchemaResult Successful Response
     * @throws ApiError
     */
    public static selectRowsSchema(
        namespace: string,
        datasetName: string,
        requestBody: SelectRowsSchemaOptions,
    ): CancelablePromise<SelectRowsSchemaResult> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/datasets/{namespace}/{dataset_name}/select_rows_schema',
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
     * @returns SelectGroupsResult Successful Response
     * @throws ApiError
     */
    public static selectGroups(
        namespace: string,
        datasetName: string,
        requestBody: SelectGroupsOptions,
    ): CancelablePromise<SelectGroupsResult> {
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

    /**
     * Serve Dataset File
     * Serve the exported dataset file.
     * @param filepath
     * @returns any Successful Response
     * @throws ApiError
     */
    public static serveDatasetFile(
        filepath: string,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/datasets/serve_dataset',
            query: {
                'filepath': filepath,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Export Dataset
     * Export the dataset to one of the supported file formats.
     * @param namespace
     * @param datasetName
     * @param requestBody
     * @returns string Successful Response
     * @throws ApiError
     */
    public static exportDataset(
        namespace: string,
        datasetName: string,
        requestBody: ExportOptions,
    ): CancelablePromise<string> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/datasets/{namespace}/{dataset_name}/export',
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
     * Get Config
     * Get the config for the dataset.
     * @param namespace
     * @param datasetName
     * @param format
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getConfig(
        namespace: string,
        datasetName: string,
        format: 'yaml' | 'json',
    ): CancelablePromise<(string | Record<string, any>)> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/datasets/{namespace}/{dataset_name}/config',
            path: {
                'namespace': namespace,
                'dataset_name': datasetName,
            },
            query: {
                'format': format,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Get Settings
     * Get the settings for the dataset.
     * @param namespace
     * @param datasetName
     * @returns DatasetSettings Successful Response
     * @throws ApiError
     */
    public static getSettings(
        namespace: string,
        datasetName: string,
    ): CancelablePromise<DatasetSettings> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/datasets/{namespace}/{dataset_name}/settings',
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
     * Update Settings
     * Update settings for the dataset.
     * @param namespace
     * @param datasetName
     * @param requestBody
     * @returns any Successful Response
     * @throws ApiError
     */
    public static updateSettings(
        namespace: string,
        datasetName: string,
        requestBody: DatasetSettings,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/datasets/{namespace}/{dataset_name}/settings',
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
     * Add Labels
     * "Add a label to the dataset.
     * @param namespace
     * @param datasetName
     * @param requestBody
     * @returns number Successful Response
     * @throws ApiError
     */
    public static addLabels(
        namespace: string,
        datasetName: string,
        requestBody: AddLabelsOptions,
    ): CancelablePromise<number> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/datasets/{namespace}/{dataset_name}/labels',
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
     * Remove Labels
     * "Add a label to the dataset.
     * @param namespace
     * @param datasetName
     * @param requestBody
     * @returns number Successful Response
     * @throws ApiError
     */
    public static removeLabels(
        namespace: string,
        datasetName: string,
        requestBody: RemoveLabelsOptions,
    ): CancelablePromise<number> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/datasets/{namespace}/{dataset_name}/labels',
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

}
