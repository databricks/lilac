/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { TaskStatus } from './TaskStatus';
import type { TaskStepInfo } from './TaskStepInfo';

/**
 * Metadata about a task.
 */
export type TaskInfo = {
    name: string;
    status: TaskStatus;
    progress?: number;
    message?: string;
    details?: string;
    step_progress?: number;
    steps?: Array<TaskStepInfo>;
    description?: string;
    start_timestamp: string;
    end_timestamp?: string;
    error?: string;
};

