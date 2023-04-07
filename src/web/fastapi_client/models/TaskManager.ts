/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { TaskInfo } from './TaskInfo';

/**
 * Manage FastAPI background tasks.
 */
export type TaskManager = {
    tasks?: Record<string, TaskInfo>;
};

