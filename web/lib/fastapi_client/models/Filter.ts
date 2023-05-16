/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { BinaryOp } from './BinaryOp';
import type { UnaryOp } from './UnaryOp';

/**
 * A filter on a column.
 */
export type Filter = {
    path: (Array<string> | string);
    op: (BinaryOp | UnaryOp);
    value?: (number | boolean | string | Blob | Array<string>);
};

