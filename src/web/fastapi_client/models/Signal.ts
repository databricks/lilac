/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Embedding } from './Embedding';

/**
 * Interface for signals to implement. A signal can score documents and a dataset column.
 */
export type Signal = {
    signal_name?: string;
    embedding?: (string | Embedding);
};

