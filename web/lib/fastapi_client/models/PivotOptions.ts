/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { BinaryFilter } from './BinaryFilter';
import type { ListFilter } from './ListFilter';
import type { StringFilter } from './StringFilter';
import type { UnaryFilter } from './UnaryFilter';

/**
 * The request for the pivot endpoint.
 */
export type PivotOptions = {
    inner_path: (Array<string> | string);
    outer_path: (Array<string> | string);
    filters?: Array<(BinaryFilter | StringFilter | UnaryFilter | ListFilter)>;
};

