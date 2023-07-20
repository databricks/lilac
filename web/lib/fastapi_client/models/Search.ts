/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptQuery } from './ConceptQuery';
import type { KeywordQuery } from './KeywordQuery';
import type { SemanticQuery } from './SemanticQuery';

/**
 * A search on a column.
 */
export type Search = {
    path: (Array<string> | string);
    query: (KeywordQuery | SemanticQuery | ConceptQuery);
};

