import {SlButton, SlIcon} from '@shoelace-style/shoelace/dist/react';
import React from 'react';
import {useAppDispatch} from '../hooks';
import {useGetManifestQuery} from '../store/apiDataset';
import {setSearchBoxOpen, setSearchBoxPages} from '../store/store';
import {Schema} from '../schema';
import {renderPath} from '../utils';

export interface EmbeddingsViewProps {
  namespace: string;
  datasetName: string;
}
export const EmbedingsView = React.memo(function EmbeddingsView({
  namespace,
  datasetName,
}: EmbeddingsViewProps): JSX.Element {
  const query = useGetManifestQuery({
    namespace,
    datasetName,
  });
  const dispatch = useAppDispatch();

  /** Open the search box on the embeddings page */
  function addEmbedding() {
    dispatch(setSearchBoxPages([{type: 'compute-embedding-index', name: 'compute embeddings'}]));
    dispatch(setSearchBoxOpen(true));
  }

  const dataSchema = query.currentData?.dataset_manifest.data_schema;
  const schema = dataSchema != null ? new Schema(dataSchema) : null;

  const embeddingLeafs = (schema?.leafs || []).filter(([_, field]) => field.dtype === 'embedding');

  const embeddingsTable = embeddingLeafs.length ? (
    <table className="table-auto">
      <thead className="text-left text-xs">
        <tr>
          <th className="py-1 font-light uppercase">Column</th>
          <th className="py-1 font-light uppercase">Provider</th>
        </tr>
      </thead>
      <tbody>
        {embeddingLeafs.map(([path, field]) => (
          <tr className="border-t" key={`${path}`}>
            <td className="py-2">{renderPath(path)}</td>
            <td className="py-2">name</td>
          </tr>
        ))}
      </tbody>
    </table>
  ) : (
    <span className="text-xs font-light">No embeddings computed</span>
  );

  return (
    <div className="flex flex-col gap-y-4">
      {embeddingsTable}
      <div className="flex">
        <SlButton variant="default" size="small" onClick={addEmbedding}>
          <SlIcon slot="prefix" name="plus"></SlIcon>
          Add Embedding
        </SlButton>
      </div>
    </div>
  );
});
