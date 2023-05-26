/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * Information about a dataset associated with a concept.
 */
export type ConceptDatasetOptions = {
    namespace: string;
    name: string;
    path: (Array<string> | string);
    num_negative_examples?: number;
};

