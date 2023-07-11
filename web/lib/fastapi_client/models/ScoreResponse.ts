/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * Response body for the score endpoint.
 */
export type ScoreResponse = {
    scores: Array<Record<string, any>>;
    model_synced: boolean;
};

