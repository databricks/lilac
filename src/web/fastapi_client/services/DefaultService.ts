/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AddDatasetOptions } from '../models/AddDatasetOptions';
import type { AddExamplesOptions } from '../models/AddExamplesOptions';
import type { SaveModelOptions } from '../models/SaveModelOptions';

import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class DefaultService {

    /**
     * List Models
     * List the models.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static listModels(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/db/list_models',
        });
    }

    /**
     * Model Info
     * List the models.
     * @param username
     * @param name
     * @returns any Successful Response
     * @throws ApiError
     */
    public static modelInfo(
        username: string,
        name: string,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/db/model_info',
            query: {
                'username': username,
                'name': name,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Load Model
     * List the models.
     * @param username
     * @param name
     * @returns any Successful Response
     * @throws ApiError
     */
    public static loadModel(
        username: string,
        name: string,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/db/load_model',
            query: {
                'username': username,
                'name': name,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Save Model
     * Save cached model to GCS.
     * @param requestBody
     * @returns any Successful Response
     * @throws ApiError
     */
    public static saveModel(
        requestBody: SaveModelOptions,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/db/save_model',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Add Examples
     * Save cached model to GCS.
     * @param requestBody
     * @returns any Successful Response
     * @throws ApiError
     */
    public static addExamples(
        requestBody: AddExamplesOptions,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/db/add_examples',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Search Examples
     * Search exmaples.
     * @param username
     * @param modelName
     * @param query
     * @returns any Successful Response
     * @throws ApiError
     */
    public static searchExamples(
        username: string,
        modelName: string,
        query: string,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/db/search_examples',
            query: {
                'username': username,
                'model_name': modelName,
                'query': query,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Add Data
     * Add data to a model.
     * @param requestBody
     * @returns any Successful Response
     * @throws ApiError
     */
    public static addData(
        requestBody: AddDatasetOptions,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/db/add_dataset',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Read Index
     * Return the index.html file.
     * @returns string Successful Response
     * @throws ApiError
     */
    public static readIndex(): CancelablePromise<string> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/{full_path}',
        });
    }

}
