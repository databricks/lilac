/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Column } from './Column';
import type { ConceptSearch } from './ConceptSearch';
import type { KeywordSearch } from './KeywordSearch';
import type { SemanticSearch } from './SemanticSearch';
import type { SortOrder } from './SortOrder';

/**
 * The request for the select rows schema endpoint.
 */
export type SelectRowsSchemaOptions = {
    columns?: Array<(Column | Array<string> | string)>;
    searches?: Array<(ConceptSearch | SemanticSearch | KeywordSearch)>;
    sort_by?: Array<(Array<string> | string)>;
    sort_order?: (SortOrder | null);
    combine_columns?: (boolean | null);
};

