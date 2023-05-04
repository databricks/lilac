/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { EnrichmentType } from './EnrichmentType';

/**
 * Information about an embedding function.
 */
export type EmbeddingInfo = {
    name: string;
    enrichment_type: EnrichmentType;
    json_schema: any;
};

