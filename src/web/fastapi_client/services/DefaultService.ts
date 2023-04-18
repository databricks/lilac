/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class DefaultService {

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
