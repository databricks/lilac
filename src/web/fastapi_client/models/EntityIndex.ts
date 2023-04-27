/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Signal } from './Signal';

/**
 * Index entities in a document.
 */
export type EntityIndex = {
    source_path: Array<(string | number)>;
    index_path: Array<(string | number)>;
    signal: Signal;
};

