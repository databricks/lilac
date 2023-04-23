/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Filter } from './Filter';
import type { SortOrder } from './SortOrder';

/**
 * The request for the select rows endpoint.
 */
export type SelectRowsOptions = {
    columns?: Array<Array<(string | number)>>;
    filters?: Array<Filter>;
    sort_by?: Array<Array<(string | number)>>;
    sort_order?: SortOrder;
    limit?: number;
    offset?: number;
};

