/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { TaskInfo } from './TaskInfo';

/**
 * Information for tasks that are running or completed.
 */
export type TaskManifest = {
    tasks: Record<string, TaskInfo>;
    progress?: (number | null);
};

