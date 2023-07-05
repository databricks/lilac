/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { OverallScore } from './OverallScore';

/**
 * Metrics for a concept.
 */
export type ConceptMetrics = {
    f1: number;
    precision: number;
    recall: number;
    roc_auc: number;
    overall: OverallScore;
};

