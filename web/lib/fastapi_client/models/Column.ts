/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptScoreSignal } from './ConceptScoreSignal';
import type { Signal } from './Signal';

/**
 * A column in the dataset DB.
 */
export type Column = {
    path: Array<(number | string)>;
    alias?: string;
    signal_udf?: (ConceptScoreSignal | Signal);
};

