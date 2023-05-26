/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Sensitivity } from './Sensitivity';

/**
 * The threshold for a concept at a given sensitivity.
 */
export type ConceptThreshold = {
    sensitivity: Sensitivity;
    threshold: number;
};

