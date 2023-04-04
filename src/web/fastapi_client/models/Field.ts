/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { DataType } from './DataType';

/**
 * Holds information for a field in the schema.
 */
export type Field = {
    repeated_field?: Field;
    fields?: Record<string, Field>;
    dtype?: DataType;
    enriched?: boolean;
    refers_to?: string;
};

