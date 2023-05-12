/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Column } from './Column';

/**
 * The request for the select rows schema endpoint.
 */
export type SelectRowsSchemaOptions = {
    columns?: Array<(string | Array<string> | Column)>;
    combine_columns?: boolean;
};

