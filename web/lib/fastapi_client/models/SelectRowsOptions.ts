/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Column } from './Column';
import type { FilterREST } from './FilterREST';
import type { SortOrder } from './SortOrder';

/**
 * The request for the select rows endpoint.
 */
export type SelectRowsOptions = {
    columns?: Array<(Array<string> | string | Column)>;
    filters?: Array<FilterREST>;
    sort_by?: Array<(Array<string> | string)>;
    sort_order?: SortOrder;
    limit?: number;
    offset?: number;
    combine_columns?: boolean;
};

