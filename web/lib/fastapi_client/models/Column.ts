/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptScoreSignal } from './ConceptScoreSignal';
import type { SemanticSearchSignal } from './SemanticSearchSignal';
import type { Signal } from './Signal';
import type { TextEmbeddingModelSignal } from './TextEmbeddingModelSignal';
import type { TextEmbeddingSignal } from './TextEmbeddingSignal';
import type { TextSignal } from './TextSignal';
import type { TextSplitterSignal } from './TextSplitterSignal';

/**
 * A column in the dataset.
 */
export type Column = {
    path: Array<string>;
    alias?: string;
    signal_udf?: (SemanticSearchSignal | ConceptScoreSignal | TextEmbeddingModelSignal | TextEmbeddingSignal | TextSplitterSignal | TextSignal | Signal);
};

