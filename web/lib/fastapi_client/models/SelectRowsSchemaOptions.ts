/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Column } from './Column';
import type { Search } from './Search';
import type { SortOrder } from './SortOrder';

/**
 * The request for the select rows schema endpoint.
 */
export type SelectRowsSchemaOptions = {
    columns?: Array<(Array<string> | string | Column)>;
    searches?: Array<Search>;
    sort_by?: Array<(Array<string> | string)>;
    sort_order?: SortOrder;
    combine_columns?: boolean;
};

