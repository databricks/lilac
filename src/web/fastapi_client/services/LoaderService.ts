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
     * Get Sources
     * Get the list of available sources.
     * @returns SourcesList Successful Response
     * @throws ApiError
     */
    public static getSources(): CancelablePromise<SourcesList> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/loader/get_sources',
        });
    }

    /**
     * Get Source Fields
     * Get the fields for a source.
     * @param sourceName
     * @returns SourceFieldsResponse Successful Response
     * @throws ApiError
     */
    public static getSourceFields(
        sourceName: string,
    ): CancelablePromise<SourceFieldsResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/loader/get_source_fields/{source_name}',
            path: {
                'source_name': sourceName,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }

}
