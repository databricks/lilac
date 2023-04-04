/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ScoreExample } from './ScoreExample';

/**
 * Request body for the score endpoint.
 */
export type ScoreBody = {
    examples: Array<ScoreExample>;
};

