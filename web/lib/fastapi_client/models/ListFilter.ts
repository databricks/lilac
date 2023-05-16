/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ListOp } from './ListOp';

/**
 * A filter on a column.
 */
export type ListFilter = {
    path: (Array<string> | string);
    op: ListOp;
    value: Array<string>;
};

