/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptDatasetInfo } from './ConceptDatasetInfo';
import type { Example } from './Example';

/**
 * A concept model. Stores all concept model drafts and manages syncing.
 */
export type ConceptModel = {
    namespace: string;
    concept_name: string;
    embedding_name: string;
    version?: number;
    negative_examples?: Record<string, Example>;
    dataset?: ConceptDatasetInfo;
};

