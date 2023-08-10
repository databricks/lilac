/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptACL } from './ConceptACL';
import type { SignalInputType } from './SignalInputType';

/**
 * Information about a concept.
 */
export type ConceptInfo = {
    namespace: string;
    name: string;
    description?: string;
    type: SignalInputType;
    drafts: Array<('main' | string)>;
    tags?: Array<string>;
    acls: ConceptACL;
};

