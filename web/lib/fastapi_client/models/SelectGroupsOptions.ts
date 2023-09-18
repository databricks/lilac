/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { GroupsSortBy } from './GroupsSortBy';
import type { SortOrder } from './SortOrder';

/**
 * The request for the select groups endpoint.
 */
export type SelectGroupsOptions = {
    leaf_path: (Array<string> | string);
    filters?: null;
    sort_by?: (GroupsSortBy | null);
    sort_order?: (SortOrder | null);
    limit?: (number | null);
    bins?: (Array<any[]> | null);
};

