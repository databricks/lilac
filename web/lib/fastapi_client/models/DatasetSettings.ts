/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { DatasetUISettings } from './DatasetUISettings';

/**
 * The persistent settings for a dataset.
 */
export type DatasetSettings = {
    ui?: DatasetUISettings;
    preferred_embedding?: (string | null);
    /**
     * A list of tags for the dataset to organize in the UI.
     */
    tags?: (Array<string> | null);
};

