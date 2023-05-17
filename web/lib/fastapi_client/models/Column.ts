/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptScoreSignal } from './ConceptScoreSignal';
import type { Signal } from './Signal';

/**
 * A column in the dataset.
 */
export type Column = {
    path: Array<string>;
    alias?: string;
    signal_udf?: (ConceptScoreSignal | Signal);
};

