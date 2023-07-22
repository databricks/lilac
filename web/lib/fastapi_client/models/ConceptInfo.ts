/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptACLs } from './ConceptACLs';
import type { SignalInputType } from './SignalInputType';

/**
 * Information about a concept.
 */
export type ConceptInfo = {
    namespace: string;
    name: string;
    type: SignalInputType;
    drafts: Array<('main' | string)>;
    acls: ConceptACLs;
};

