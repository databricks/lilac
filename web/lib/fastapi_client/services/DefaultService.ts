/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ServerStatusResponse } from '../models/ServerStatusResponse';

import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class DefaultService {

    /**
     * Server Status
     * Returns the server status.
     * @returns ServerStatusResponse Successful Response
     * @throws ApiError
     */
    public static serverStatus(): CancelablePromise<ServerStatusResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/status',
        });
    }

}
