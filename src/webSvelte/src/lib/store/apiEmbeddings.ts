import { EmbeddingsService } from '$lilac';
import { createApiQuery } from './apiUtils';

const EMBEDDINGS_TAG = 'embeddings';

export const useGetEmbeddingsQuery = createApiQuery(
  EmbeddingsService.getEmbeddings,
  EMBEDDINGS_TAG
);
