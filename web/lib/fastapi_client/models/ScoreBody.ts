/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ScoreExample } from './ScoreExample';
import type { Sensitivity } from './Sensitivity';

/**
 * Request body for the score endpoint.
 */
export type ScoreBody = {
    examples: Array<ScoreExample>;
    draft?: string;
    sensitivity?: Sensitivity;
};

