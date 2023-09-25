/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class SqliteService {

    /**
     * Get Tables
     * List the table names in sqlite.
     * @param dbFile
     * @returns string Successful Response
     * @throws ApiError
     */
    public static getTables(
        dbFile: string,
    ): CancelablePromise<Array<string>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/sqlite/tables',
            query: {
                'db_file': dbFile,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }

}
