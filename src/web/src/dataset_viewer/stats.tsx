import {SlAlert, SlIcon, SlSpinner} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {Schema, UUID_COLUMN} from '../schema';
import {useGetManifestQuery} from '../store/apiDataset';
import {renderPath} from '../utils';
import {LeafStats} from './LeafStats';

export interface StatsProps {
  namespace: string;
  datasetName: string;
}

export const Stats = React.memo(function Stats({namespace, datasetName}: StatsProps): JSX.Element {
  const {currentData, isFetching, error} = useGetManifestQuery({namespace, datasetName});
  if (isFetching) {
    return (
      <div className="flex items-center">
        <SlSpinner />
        <div className="pl-2">Loading dataset...</div>
      </div>
    );
  }
  <div className="error">{error != null ? `Error fetching manifest: ${error}` : ''}</div>;
  if (currentData == null) {
    return (
      <SlAlert variant="danger" open>
        <>
          <SlIcon slot="icon" name="exclamation-octagon" />
          {error}
        </>
      </SlAlert>
    );
  }
  const datasetManifest = currentData.dataset_manifest;
  const datasetId = `${datasetManifest.namespace}/${datasetManifest.dataset_name}`;
  const schema = new Schema(datasetManifest.data_schema);
  const leafStats: JSX.Element[] = [];

  for (const [leafPath] of schema.leafs) {
    if (leafPath[0] == UUID_COLUMN) {
      continue;
    }
    leafStats.push(
      <div key={`${datasetId}_${leafPath}`}>
        <div className="flex">
          <div className="field">{renderPath(leafPath)}</div>
        </div>
        <LeafStats
          namespace={namespace}
          datasetName={datasetName}
          leafPath={leafPath}
          manifest={datasetManifest}
        ></LeafStats>
      </div>
    );
  }

  return <>{leafStats}</>;
});
