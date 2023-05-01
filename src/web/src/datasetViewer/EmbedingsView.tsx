import {SlButton, SlIcon} from '@shoelace-style/shoelace/dist/react';
import React from 'react';
import {useAppDispatch} from '../hooks';
import {useGetManifestQuery} from '../store/apiDataset';
import {setSearchBoxOpen, setSearchBoxPages} from '../store/store';

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

  const embeddingManifest = query.data?.dataset_manifest?.embedding_manifest?.indexes ?? [];

  const embeddingsTable = embeddingManifest.length ? (
    <table className="table-auto">
      <thead className="text-left text-xs">
        <tr>
          <th className="py-1 font-light uppercase">Column</th>
          <th className="py-1 font-light uppercase">Provider</th>
        </tr>
      </thead>
      <tbody>
        {embeddingManifest.map((embeddingIndex) => (
          <tr
            className="border-t"
            key={`${embeddingIndex.column}.${embeddingIndex.embedding.embedding_name}`}
          >
            <td className="py-2">{embeddingIndex.column}</td>
            <td className="py-2">{embeddingIndex.embedding.embedding_name}</td>
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
