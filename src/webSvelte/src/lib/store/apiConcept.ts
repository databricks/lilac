import {ConceptsService} from '$lilac';
import {createApiQuery} from './apiUtils';

const CONCEPTS_TAG = 'concepts';

export const useGetConceptQuery = createApiQuery(ConceptsService.getConcept, CONCEPTS_TAG);
