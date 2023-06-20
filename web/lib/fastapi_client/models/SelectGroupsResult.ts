/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * The result of a select groups query.
 */
export type SelectGroupsResult = {
    too_many_distinct: boolean;
    counts: Array<Array<any>>;
    bins?: Array<Array<any>>;
};

