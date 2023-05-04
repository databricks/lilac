/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptScoreSignal } from './ConceptScoreSignal';
import type { Signal } from './Signal';

/**
 * Computes a signal transformation over a field.
 */
export type SignalTransform = {
    signal: (ConceptScoreSignal | Signal);
};

