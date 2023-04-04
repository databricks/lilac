/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { LabeledExample } from './LabeledExample';

/**
 * The request for the save model to GCS endpoint.
 */
export type SaveModelOptions = {
    username: string;
    name: string;
    labeled_data: Array<LabeledExample>;
};

