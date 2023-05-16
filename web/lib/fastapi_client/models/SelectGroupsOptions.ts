/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { BinaryFilter } from './BinaryFilter';
import type { GroupsSortBy } from './GroupsSortBy';
import type { ListFilter } from './ListFilter';
import type { NamedBins } from './NamedBins';
import type { SortOrder } from './SortOrder';
import type { UnaryFilter } from './UnaryFilter';

/**
 * The request for the select groups endpoint.
 */
export type SelectGroupsOptions = {
    leaf_path: Array<(number | string)>;
    filters?: Array<(BinaryFilter | UnaryFilter | ListFilter)>;
    sort_by?: GroupsSortBy;
    sort_order?: SortOrder;
    limit?: number;
    bins?: (Array<number> | NamedBins);
};

