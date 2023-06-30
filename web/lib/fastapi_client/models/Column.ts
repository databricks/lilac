/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptLabelsSignal } from './ConceptLabelsSignal';
import type { ConceptScoreSignal } from './ConceptScoreSignal';
import type { Signal } from './Signal';
import type { SubstringSignal } from './SubstringSignal';
import type { TextEmbeddingModelSignal } from './TextEmbeddingModelSignal';
import type { TextEmbeddingSignal } from './TextEmbeddingSignal';
import type { TextSignal } from './TextSignal';

/**
 * A column in the dataset.
 */
export type Column = {
    path: Array<string>;
    alias?: string;
    signal_udf?: (ConceptScoreSignal | ConceptLabelsSignal | SubstringSignal | TextEmbeddingModelSignal | TextEmbeddingSignal | TextSignal | Signal);
};

