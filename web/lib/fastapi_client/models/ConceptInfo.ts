/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { SignalInputType } from './SignalInputType';

/**
 * Information about a concept.
 */
export type ConceptInfo = {
    namespace: string;
    name: string;
    input_type: SignalInputType;
};

