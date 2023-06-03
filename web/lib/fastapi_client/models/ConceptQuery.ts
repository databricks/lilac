/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * A concept search query on a column.
 */
export type ConceptQuery = {
    type: 'concept';
    concept_namespace: string;
    concept_name: string;
    embedding: string;
};

