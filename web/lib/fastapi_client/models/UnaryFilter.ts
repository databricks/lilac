/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { UnaryOp } from './UnaryOp';

/**
 * A filter on a column.
 */
export type UnaryFilter = {
    path: (Array<string> | string);
    op: UnaryOp;
    value?: null;
};

