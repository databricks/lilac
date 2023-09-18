/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { SortOrder } from './SortOrder';

/**
 * The request for the select rows endpoint.
 */
export type SelectRowsOptions = {
    columns?: null;
    searches?: null;
    filters?: null;
    sort_by?: null;
    sort_order?: (SortOrder | null);
    limit?: (number | null);
    offset?: (number | null);
    combine_columns?: (boolean | null);
};

