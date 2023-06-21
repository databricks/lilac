/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * A concept model. Stores all concept model drafts and manages syncing.
 */
export type ConceptModel = {
    namespace: string;
    concept_name: string;
    embedding_name: string;
    version?: number;
};

