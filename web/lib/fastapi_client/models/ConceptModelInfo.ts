/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptColumnInfo } from './ConceptColumnInfo';

/**
 * Information about a concept model.
 */
export type ConceptModelInfo = {
    namespace: string;
    concept_name: string;
    embedding_name: string;
    version: number;
    column_info?: ConceptColumnInfo;
};

