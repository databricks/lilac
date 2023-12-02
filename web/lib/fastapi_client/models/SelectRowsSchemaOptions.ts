/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptSearch } from './ConceptSearch';
import type { KeywordSearch } from './KeywordSearch';
import type { lilac__router_dataset__Column } from './lilac__router_dataset__Column';
import type { MetadataSearch } from './MetadataSearch';
import type { SemanticSearch } from './SemanticSearch';
import type { SortOrder } from './SortOrder';

/**
 * The request for the select rows schema endpoint.
 */
export type SelectRowsSchemaOptions = {
    columns?: Array<(lilac__router_dataset__Column | Array<string> | string)>;
    searches?: Array<(ConceptSearch | SemanticSearch | KeywordSearch | MetadataSearch)>;
    sort_by?: Array<(Array<string> | string)>;
    sort_order?: (SortOrder | null);
    combine_columns?: (boolean | null);
};

