/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * The request for the cluster endpoint.
 */
export type ClusterOptions = {
    input: (Array<string> | string);
    output_path?: (Array<string> | string | null);
    /**
     * Accelerate computation by running remotely on Lilac Garden.
     */
    use_garden?: boolean;
    overwrite?: boolean;
};

