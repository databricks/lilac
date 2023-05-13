/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { SignalInputType } from './SignalInputType';

/**
 * Information about an embedding function.
 */
export type EmbeddingInfo = {
    name: string;
    input_type: SignalInputType;
    json_schema: Record<string, any>;
};

