/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * The request for the create model spec endpoint.
 */
export type AddDatasetOptions = {
    username: string;
    model_name: string;
    hf_dataset: string;
    hf_split?: string;
    hf_text_field?: string;
};

