/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AuthenticationInfo } from '../models/AuthenticationInfo';
import type { ServerStatus } from '../models/ServerStatus';

import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class DefaultService {

    /**
     * Auth Info
     * Returns the user's ACL.
     *
     * NOTE: Validation happens server-side as well. This is just used for UI treatment.
     * @returns AuthenticationInfo Successful Response
     * @throws ApiError
     */
    public static authInfo(): CancelablePromise<AuthenticationInfo> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/auth_info',
        });
    }

    /**
     * Status
     * Returns server status information.
     * @returns ServerStatus Successful Response
     * @throws ApiError
     */
    public static status(): CancelablePromise<ServerStatus> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/status',
        });
    }

    /**
     * Load Config
     * Loads from the lilac.yml.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static loadConfig(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/load_config',
        });
    }

}
