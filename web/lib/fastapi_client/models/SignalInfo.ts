/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { SignalInputType } from './SignalInputType';

/**
 * Information about a signal.
 */
export type SignalInfo = {
    name: string;
    input_type: SignalInputType;
    json_schema: Record<string, any>;
};

