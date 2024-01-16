/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { PivotResultOuterGroup } from './PivotResultOuterGroup';

/**
 * The result of a pivot query.
 */
export type PivotResult = {
    outer_groups: Array<PivotResultOuterGroup>;
    too_many_distinct?: boolean;
};

