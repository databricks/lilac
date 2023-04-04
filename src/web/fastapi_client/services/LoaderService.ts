/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SourceFieldsResponse } from '../models/SourceFieldsResponse';
import type { SourcesList } from '../models/SourcesList';

import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class LoaderService {

    /**
     * Sources
     * Get the list of available sources.
     * @returns SourcesList Successful Response
     * @throws ApiError
     */
    public static loaderSources(): CancelablePromise<SourcesList> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/loader/sources',
        });
    }

    /**
     * Source Fields
     * Get the list of available sources.
     * @param sourceName
     * @returns SourceFieldsResponse Successful Response
     * @throws ApiError
     */
    public static loaderSourceFields(
        sourceName: string,
    ): CancelablePromise<SourceFieldsResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/loader/source_fields/{source_name}',
            path: {
                'source_name': sourceName,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }

}
