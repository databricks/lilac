/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { SourceField } from './SourceField';

/**
 * The interface to the /process_source endpoint.
 */
export type SourceFieldsResponse = {
    fields: Array<SourceField>;
};

