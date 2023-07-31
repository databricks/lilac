/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * Response body for the score endpoint.
 */
export type ScoreResponse = {
    scored_spans: Array<Array<Record<string, any>>>;
    model_synced: boolean;
};

