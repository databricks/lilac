/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { BucketizeTransform } from './BucketizeTransform';
import type { SignalTransform } from './SignalTransform';

/**
 * A column in the dataset DB.
 */
export type Column = {
    feature: Array<(number | string)>;
    alias: string;
    transform?: (BucketizeTransform | SignalTransform);
};

