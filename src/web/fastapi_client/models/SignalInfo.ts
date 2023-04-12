/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { EnrichmentType } from './EnrichmentType';

/**
 * Information about a signal.
 */
export type SignalInfo = {
    name: string;
    enrichment_type: EnrichmentType;
    embedding_based: boolean;
    json_schema: any;
};

