/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ClusterInputSelectorConfig } from './ClusterInputSelectorConfig';

/**
 * The request for the cluster endpoint.
 */
export type ClusterOptions = {
    input?: (Array<string> | string | null);
    input_selector?: (ClusterInputSelectorConfig | null);
    output_path?: (Array<string> | string | null);
    /**
     * Accelerate computation by running remotely on Lilac Garden.
     */
    use_garden?: boolean;
    overwrite?: boolean;
};

