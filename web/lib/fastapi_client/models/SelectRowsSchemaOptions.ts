/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Column } from './Column';
import type { Search } from './Search';

/**
 * The request for the select rows schema endpoint.
 */
export type SelectRowsSchemaOptions = {
    columns?: Array<(Array<string> | string | Column)>;
    searches?: Array<Search>;
    combine_columns?: boolean;
};

