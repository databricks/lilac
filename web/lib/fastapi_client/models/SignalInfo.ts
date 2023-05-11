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
    json_schema: Record<string, any>;
};

