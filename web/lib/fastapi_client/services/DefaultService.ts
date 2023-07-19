/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { UserAccess } from '../models/UserAccess';

import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class DefaultService {

    /**
     * User Acls
     * Returns the user's ACLs.
     *
     * NOTE: Validation happens server-side as well. This is just used for UI treatment.
     * @returns UserAccess Successful Response
     * @throws ApiError
     */
    public static userAcls(): CancelablePromise<UserAccess> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/acl',
        });
    }

}
