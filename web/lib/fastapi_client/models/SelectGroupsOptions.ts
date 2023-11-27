/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { BinaryFilter } from './BinaryFilter';
import type { GroupsSortBy } from './GroupsSortBy';
import type { ListFilter } from './ListFilter';
import type { SortOrder } from './SortOrder';
import type { StringFilter } from './StringFilter';
import type { UnaryFilter } from './UnaryFilter';

/**
 * The request for the select groups endpoint.
 */
export type SelectGroupsOptions = {
    leaf_path: (Array<string> | string);
    filters?: Array<(BinaryFilter | StringFilter | UnaryFilter | ListFilter)>;
    sort_by?: (GroupsSortBy | null);
    sort_order?: (SortOrder | null);
    limit?: (number | null);
    bins?: (Array<any[]> | null);
};

