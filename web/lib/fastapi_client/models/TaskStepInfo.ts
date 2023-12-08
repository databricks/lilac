/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * Information about a step of the task..
 */
export type TaskStepInfo = {
    progress?: (number | null);
    description?: (string | null);
    it_idx?: (number | null);
    estimated_len?: (number | null);
    estimated_total_sec?: (number | null);
    elapsed_sec?: (number | null);
    it_per_sec?: (number | null);
    start_time?: (number | null);
    shard_progresses?: Array<any[]>;
};

