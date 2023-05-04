import { ConceptsService } from '../fastapi_client';
import { createApiQuery } from './apiUtils';

const CONCEPTS_TAG = 'concepts';

export const useGetConceptQuery = createApiQuery(ConceptsService.getConcept, CONCEPTS_TAG);
