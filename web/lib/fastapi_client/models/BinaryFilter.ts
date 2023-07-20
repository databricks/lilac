/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { BinaryOp } from './BinaryOp';

/**
 * A filter on a column.
 */
export type BinaryFilter = {
    path: (Array<string> | string);
    op: BinaryOp;
    value: (number | boolean | string | Blob);
};

