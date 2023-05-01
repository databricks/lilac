/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Signal } from './Signal';

/**
 * Index entities in a document.
 */
export type EntityIndex = {
    source_path: Array<(number | string)>;
    index_path: Array<(number | string)>;
    signal: Signal;
};

