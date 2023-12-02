import {RagService} from '$lilac';
import {createApiQuery} from './queryUtils';

export const RAG_TAG = 'rag';

export const getRagRetrieval = createApiQuery(RagService.retrieval, RAG_TAG);
export const getRagGeneration = createApiQuery(RagService.generate, RAG_TAG);
