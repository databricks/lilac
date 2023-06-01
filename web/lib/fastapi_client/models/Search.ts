/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { SearchType } from './SearchType';

/**
 * A search on a column.
 */
export type Search = {
    path: (Array<string> | string);
    type: SearchType;
    query: string;
    embedding?: string;
};

