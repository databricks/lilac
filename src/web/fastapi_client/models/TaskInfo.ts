/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { TaskStatus } from './TaskStatus';

/**
 * Metadata about a task.
 */
export type TaskInfo = {
    name: string;
    status: TaskStatus;
    progress?: number;
    description?: string;
    start_timestamp: string;
    end_timestamp?: string;
    error?: string;
};

