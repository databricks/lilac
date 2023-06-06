/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { SortOrder } from './SortOrder';

/**
 * The information about what is sorted after combining searches and explicit sorts.
 */
export type SortResult = {
    path: Array<string>;
    order: SortOrder;
    alias?: string;
    search_index?: number;
};

