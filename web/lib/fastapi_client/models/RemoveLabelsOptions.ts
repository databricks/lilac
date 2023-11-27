/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { BinaryFilter } from './BinaryFilter';
import type { ConceptSearch } from './ConceptSearch';
import type { KeywordSearch } from './KeywordSearch';
import type { ListFilter } from './ListFilter';
import type { MetadataSearch } from './MetadataSearch';
import type { SemanticSearch } from './SemanticSearch';
import type { StringFilter } from './StringFilter';
import type { UnaryFilter } from './UnaryFilter';

/**
 * The request for the remove labels endpoint.
 */
export type RemoveLabelsOptions = {
    label_name: string;
    row_ids?: Array<string>;
    searches?: Array<(ConceptSearch | SemanticSearch | KeywordSearch | MetadataSearch)>;
    filters?: Array<(BinaryFilter | StringFilter | UnaryFilter | ListFilter)>;
};

