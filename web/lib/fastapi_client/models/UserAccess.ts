/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { ConceptUserAccess } from './ConceptUserAccess';
import type { DatasetUserAccess } from './DatasetUserAccess';

/**
 * User access.
 */
export type UserAccess = {
    create_dataset: boolean;
    dataset: DatasetUserAccess;
    concept: ConceptUserAccess;
};

