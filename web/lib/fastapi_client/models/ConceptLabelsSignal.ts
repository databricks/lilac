/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * Computes spans where text is labeled for the concept, either positive or negative.
 */
export type ConceptLabelsSignal = {
    signal_name: 'concept_labels';
    output_type?: ('embedding' | 'cluster' | null);
    map_batch_size?: number;
    map_parallelism?: number;
    map_strategy?: 'processes' | 'threads';
    namespace: string;
    concept_name: string;
    version?: (number | null);
    draft?: string;
};

