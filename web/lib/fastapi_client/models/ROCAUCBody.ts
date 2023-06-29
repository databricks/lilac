/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptColumnInfo } from './ConceptColumnInfo';

/**
 * Request body for the compute_roc_auc endpoint.
 */
export type ROCAUCBody = {
    column_info?: ConceptColumnInfo;
};

