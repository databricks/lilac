/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Filter } from './Filter';
import type { SortOrder } from './SortOrder';

/**
 * The request for the select rows endpoint.
 */
export type SelectRowsOptions = {
    columns?: Array<string>;
    filters?: Array<Filter>;
    sort_by?: Array<string>;
    sort_order?: SortOrder;
    limit?: number;
    offset?: number;
};

