/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * Computes spans where text is labeled for the concept, either positive or negative.
 */
export type ConceptLabelsSignal = {
    signal_name: 'concept_labels';
    namespace: string;
    concept_name: string;
    draft?: string;
};

