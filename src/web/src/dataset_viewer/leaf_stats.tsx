import {SlSpinner} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {DatasetManifest} from '../../fastapi_client';
import {useTopValues} from '../hooks/useTopValues';
import {Path, Schema} from '../schema';
import {Histogram} from './histogram';

const MAX_NUM_GROUPS_TO_RENDER = 20;

export interface LeafStatsProps {
  namespace: string;
  datasetName: string;
  leafPath: Path;
  manifest: DatasetManifest;
}

export const LeafStats = React.memo(function LeafStats({
  leafPath,
  namespace,
  datasetName,
  manifest,
}: LeafStatsProps): JSX.Element {
  const schema = new Schema(manifest.data_schema);
  const field = schema.getLeaf(leafPath);
  const topK = MAX_NUM_GROUPS_TO_RENDER;
  const {isFetching, values, tooManyDistinct, dtypeNotSupported, onlyTopK, statsResult} =
    useTopValues({namespace, datasetName, leafPath, field, topK: MAX_NUM_GROUPS_TO_RENDER});
  if (isFetching) {
    return <SlSpinner />;
  }
  if (tooManyDistinct) {
    return (
      <div className="error">
        Too many distinct values: {statsResult?.approx_count_distinct.toLocaleString()}
      </div>
    );
  }
  if (dtypeNotSupported) {
    return <div className="error">"{field.dtype}" dtype is not yet supported.</div>;
  }
  return (
    <>
      {onlyTopK && <div>Showing only the top {topK} values.</div>}
      <Histogram values={values}></Histogram>
    </>
  );
});
