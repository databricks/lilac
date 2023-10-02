/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptUserAccess } from './ConceptUserAccess';
import type { DatasetUserAccess } from './DatasetUserAccess';

/**
 * User access.
 */
export type UserAccess = {
    is_admin?: boolean;
    create_dataset: boolean;
    dataset: DatasetUserAccess;
    concept: ConceptUserAccess;
};

