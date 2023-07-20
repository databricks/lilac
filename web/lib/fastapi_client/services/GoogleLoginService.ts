/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class GoogleLoginService {

    /**
     * Login
     * Redirects to Google OAuth login page.
     * @param originUrl
     * @returns any Successful Response
     * @throws ApiError
     */
    public static login(
        originUrl: string,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/google/login',
            query: {
                'origin_url': originUrl,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Auth
     * Handles the Google OAuth callback.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static auth(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/google/auth',
        });
    }

    /**
     * Logout
     * Logs the user out.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static logout(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/google/logout',
        });
    }

}
