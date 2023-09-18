/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * A concept search query on a column.
 */
export type ConceptSearch = {
    path: (Array<string> | string);
    concept_namespace: string;
    concept_name: string;
    embedding: string;
    type?: 'concept';
};

