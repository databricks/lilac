/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ClusterInputFormatSelectorInfo } from './ClusterInputFormatSelectorInfo';

/**
 * Holds information about clustering operation that was run on a dataset.
 */
export type ClusterInfo = {
    min_cluster_size?: (number | null);
    use_garden?: (boolean | null);
    input_path?: (Array<string> | null);
    input_format_selector?: (ClusterInputFormatSelectorInfo | null);
};

