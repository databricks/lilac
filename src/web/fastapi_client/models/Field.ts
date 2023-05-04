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
    signal_root?: boolean;
    is_entity?: boolean;
    derived_from?: Array<(number | string)>;
};

