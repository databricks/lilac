/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TaskManifest } from '../models/TaskManifest';

import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class TasksService {

    /**
     * Get Task Manifest
     * Get the tasks, both completed and pending.
     * @returns TaskManifest Successful Response
     * @throws ApiError
     */
    public static getTaskManifest(): CancelablePromise<TaskManifest> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/tasks/',
        });
    }

}
