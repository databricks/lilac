/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { DataType } from './DataType';
import type { Field } from './Field';

/**
 * The map dtype parameterized by the key and value types.
 */
export type MapType = {
    type: 'map';
    key_type: DataType;
    value_field: Field;
};

