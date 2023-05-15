/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { TextEmbeddingSignal } from './TextEmbeddingSignal';
import type { TextSplitterSignal } from './TextSplitterSignal';

/**
 * Compute scores along a "concept" for documents.
 */
export type ConceptScoreSignal = {
    signal_name?: string;
    split?: string;
    split_signal?: TextSplitterSignal;
    embedding: string;
    embedding_signal?: TextEmbeddingSignal;
    namespace: string;
    concept_name: string;
};

