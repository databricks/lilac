/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { BinaryFilter } from './BinaryFilter';
import type { Column } from './Column';
import type { ConceptSearch } from './ConceptSearch';
import type { KeywordSearch } from './KeywordSearch';
import type { ListFilter } from './ListFilter';
import type { SemanticSearch } from './SemanticSearch';
import type { SortOrder } from './SortOrder';
import type { UnaryFilter } from './UnaryFilter';

/**
 * The request for the select rows endpoint.
 */
export type SelectRowsOptions = {
    columns?: Array<(Column | Array<string> | string)>;
    searches?: Array<(ConceptSearch | SemanticSearch | KeywordSearch)>;
    filters?: Array<(BinaryFilter | UnaryFilter | ListFilter)>;
    sort_by?: Array<(Array<string> | string)>;
    sort_order?: (SortOrder | null);
    limit?: (number | null);
    offset?: (number | null);
    combine_columns?: (boolean | null);
};

