/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptDatasetInfo } from './ConceptDatasetInfo';
import type { ScoreExample } from './ScoreExample';
import type { Sensitivity } from './Sensitivity';

/**
 * Request body for the score endpoint.
 */
export type ScoreBody = {
    examples: Array<ScoreExample>;
    draft?: string;
    dataset: ConceptDatasetInfo;
    sensitivity?: Sensitivity;
};

