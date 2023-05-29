/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptDatasetInfo } from './ConceptDatasetInfo';

/**
 * A concept model. Stores all concept model drafts and manages syncing.
 */
export type ConceptModel = {
    namespace: string;
    concept_name: string;
    embedding_name: string;
    version?: number;
    dataset_info?: ConceptDatasetInfo;
};

