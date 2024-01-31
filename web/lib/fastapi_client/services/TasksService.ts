/* generated using openapi-typescript-codegen -- do no edit */
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

    /**
     * Cancel Task
     * Cancel a task.
     * @param taskId
     * @returns any Successful Response
     * @throws ApiError
     */
    public static cancelTask(
        taskId: string,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/tasks/{task_id}/cancel',
            path: {
                'task_id': taskId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }

}
