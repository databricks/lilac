/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { BaseModel } from './BaseModel';
import type { Source } from './Source';

/**
 * Options for loading a dataset.
 */
export type LoadDatasetShardOptions = {
    source: Source;
    shard_info: BaseModel;
};

