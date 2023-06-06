/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { SortOrder } from './SortOrder';

/**
 * The result of a column sort query.
 */
export type SortResult = {
    path: Array<string>;
    order: SortOrder;
    alias?: string;
    search_index?: number;
};

