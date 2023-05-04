/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Filter } from './Filter';
import type { GroupsSortBy } from './GroupsSortBy';
import type { NamedBins } from './NamedBins';
import type { SortOrder } from './SortOrder';

/**
 * The request for the select groups endpoint.
 */
export type SelectGroupsOptions = {
    leaf_path: Array<(number | string)>;
    filters?: Array<Filter>;
    sort_by?: GroupsSortBy;
    sort_order?: SortOrder;
    limit?: number;
    bins?: (Array<number> | NamedBins);
};

