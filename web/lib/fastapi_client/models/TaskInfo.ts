/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { TaskStatus } from './TaskStatus';
import type { TaskStepInfo } from './TaskStepInfo';
import type { TaskType } from './TaskType';

/**
 * Metadata about a task.
 */
export type TaskInfo = {
    name: string;
    type?: (TaskType | null);
    status: TaskStatus;
    progress?: (number | null);
    message?: (string | null);
    details?: (string | null);
    step_progress?: (number | null);
    steps?: (Array<TaskStepInfo> | null);
    description?: (string | null);
    start_timestamp: string;
    end_timestamp?: (string | null);
    error?: (string | null);
};

