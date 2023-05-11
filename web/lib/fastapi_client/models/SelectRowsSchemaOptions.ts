/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Column } from './Column';

/**
 * The request for the select rows schema endpoint.
 */
export type SelectRowsSchemaOptions = {
    columns?: Array<(Array<string> | Column)>;
    combine_columns?: boolean;
};

