/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Example } from './Example';
import type { SignalInputType } from './SignalInputType';

/**
 * A concept is a collection of examples. This is the public API.
 */
export type Concept = {
    namespace?: string;
    concept_name: string;
    type: SignalInputType;
    data: Record<string, Record<string, Example>>;
    version?: number;
};

