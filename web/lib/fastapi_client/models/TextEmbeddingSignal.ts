/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { TextSplitterSignal } from './TextSplitterSignal';

/**
 * An interface for signals that compute embeddings for text.
 */
export type TextEmbeddingSignal = {
    signal_name?: string;
    split?: string;
    split_signal?: TextSplitterSignal;
};

