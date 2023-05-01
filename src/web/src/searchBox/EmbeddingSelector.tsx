import {JSONSchema7} from 'json-schema';
import {useParams} from 'react-router-dom';
import {EmbeddingInfo} from '../../fastapi_client';
import {useGetEmbeddingsQuery} from '../store/apiEmbeddings';
import {renderQuery} from '../utils';
import {SearchBoxItem} from './SearchBoxItem';

export function EmbeddingSelector({onSelect}: {onSelect: (embedding: EmbeddingInfo) => void}) {
  const {namespace, datasetName} = useParams<{namespace: string; datasetName: string}>();
  if (namespace == null || datasetName == null) {
    throw new Error('Invalid route');
  }
  const query = useGetEmbeddingsQuery();
  return renderQuery(query, (embeddings) => {
    return (
      <>
        {embeddings.map((embedding) => {
          const jsonSchema = embedding.json_schema as JSONSchema7;
          return (
            <SearchBoxItem key={embedding.name} onSelect={() => onSelect(embedding)}>
              <div className="flex w-full justify-between">
                <div className="truncate">{embedding.name}</div>
                <div className="truncate">{jsonSchema.description}</div>
              </div>
            </SearchBoxItem>
          );
        })}
      </>
    );
  });
}
