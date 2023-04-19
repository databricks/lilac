/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { EnrichmentType } from './EnrichmentType';

/**
 * Information about a concept.
 */
export type ConceptInfo = {
    namespace: string;
    name: string;
    enrichment_type: EnrichmentType;
};

