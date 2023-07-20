/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AuthenticationInfo } from '../models/AuthenticationInfo';

import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class DefaultService {

    /**
     * Auth Info
     * Returns the user's ACLs.
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

}
