/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { TaskShardInfo } from './TaskShardInfo';
import type { TaskStatus } from './TaskStatus';
import type { TaskType } from './TaskType';

export type TaskInfo = {
    name: string;
    start_timestamp: string;
    end_timestamp?: (string | null);
    type?: (TaskType | null);
    status?: TaskStatus;
    message?: (string | null);
    details?: (string | null);
    shards?: Record<string, TaskShardInfo>;
    description?: (string | null);
    error?: (string | null);
    total_len?: (number | null);
    total_progress?: (number | null);
};

