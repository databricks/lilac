import {SlSpinner} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {DatasetManifest, DataType} from '../../fastapi_client';
import {getEqualBins, TOO_MANY_DISTINCT} from '../db';
import {isOrdinal, Path, Schema} from '../schema';
import {useGetStatsQuery} from '../store/api_dataset';
import {renderError} from '../utils';
import {Histogram} from './histogram';

export interface LeafStatsProps {
  namespace: string;
  datasetName: string;
  leafPath: Path;
  manifest: DatasetManifest;
}
const NUM_AUTO_BINS = 20;
const SUPPORTED_DTYPES: DataType[] = [
  'string',
  'int8',
  'int16',
  'int32',
  'int64',
  'uint8',
  'uint16',
  'uint32',
  'uint64',
  'float16',
  'float32',
  'float64',
];

export const LeafStats = React.memo(function LeafStats({
  leafPath,
  namespace,
  datasetName,
  manifest,
}: LeafStatsProps): JSX.Element {
  // Fetch stats.
  const stats = useGetStatsQuery({namespace, datasetName, options: {leaf_path: leafPath}});
  if (stats.isFetching) {
    return <SlSpinner />;
  }
  if (stats.error) {
    return renderError(stats.error);
  }
  if (stats.currentData == null) {
    return <div className="error">Stats was null</div>;
  }
  const {approx_count_distinct} = stats.currentData;
  if (approx_count_distinct >= TOO_MANY_DISTINCT) {
    return <div className="error">Too many distinct values: {approx_count_distinct}</div>;
  }
  const schema = new Schema(manifest.data_schema);
  const field = schema.getLeaf(leafPath);
  if (field != null && !SUPPORTED_DTYPES.includes(field.dtype!)) {
    return <div className="error">"{field.dtype}" dtype is not yet supported.</div>;
  }
  let bins: number[] | undefined = undefined;
  if (isOrdinal(field.dtype!)) {
    bins = getEqualBins(stats.currentData, leafPath, NUM_AUTO_BINS);
  }
  return (
    <Histogram
      namespace={namespace}
      datasetName={datasetName}
      leafPath={leafPath}
      bins={bins}
    ></Histogram>
  );
});
