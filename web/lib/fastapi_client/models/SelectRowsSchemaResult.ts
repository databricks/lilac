/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Schema } from './Schema';
import type { SearchResultInfo } from './SearchResultInfo';
import type { SortResult } from './SortResult';

/**
 * The result of a select rows schema query.
 */
export type SelectRowsSchemaResult = {
    data_schema: Schema;
    alias_udf_paths?: Record<string, Array<string>>;
    search_results?: Array<SearchResultInfo>;
    sorts?: Array<SortResult>;
};

