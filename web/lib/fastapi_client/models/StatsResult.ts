/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * The result of a stats() query.
 */
export type StatsResult = {
    path: Array<string>;
    total_count: number;
    approx_count_distinct: number;
    min_val?: (number | string | null);
    max_val?: (number | string | null);
    avg_text_length?: (number | null);
};

