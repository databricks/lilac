/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Comparison } from './Comparison';

/**
 * A filter on a column.
 */
export type Filter = {
    path: Array<(number | string)>;
    comparison: Comparison;
    value: (number | boolean | string | Blob);
};

