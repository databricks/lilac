/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptLabelsSignal } from './ConceptLabelsSignal';
import type { ConceptSignal } from './ConceptSignal';
import type { SemanticSimilaritySignal } from './SemanticSimilaritySignal';
import type { Signal } from './Signal';
import type { SubstringSignal } from './SubstringSignal';
import type { TextEmbeddingSignal } from './TextEmbeddingSignal';
import type { TextSignal } from './TextSignal';

/**
 * A column in the dataset.
 */
export type Column = {
    path: Array<string>;
    alias?: string;
    signal_udf?: (ConceptSignal | ConceptLabelsSignal | SubstringSignal | SemanticSimilaritySignal | TextEmbeddingSignal | TextSignal | Signal);
};

