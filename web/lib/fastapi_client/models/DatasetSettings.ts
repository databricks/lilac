/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { DatasetUISettings } from './DatasetUISettings';

/**
 * The persistent settings for a dataset.
 */
export type DatasetSettings = {
    ui?: DatasetUISettings;
    preferred_embedding?: string;
};

