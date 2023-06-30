/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptColumnInfo } from './ConceptColumnInfo';

/**
 * Request body for the compute_metrics endpoint.
 */
export type MetricsBody = {
    column_info?: ConceptColumnInfo;
};

