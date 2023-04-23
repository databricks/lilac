/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { BucketizeTransform } from './BucketizeTransform';
import type { ConceptTransform } from './ConceptTransform';
import type { SignalTransform } from './SignalTransform';

/**
 * A column in the dataset DB.
 */
export type Column = {
    feature: Array<(string | number)>;
    alias: string;
    transform?: (ConceptTransform | BucketizeTransform | SignalTransform);
};

