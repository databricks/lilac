/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Field } from './Field';

/**
 * Database schema.
 */
export type Schema = {
    fields: Record<string, Field>;
};

