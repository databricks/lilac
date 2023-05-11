import {ConceptsService} from '$lilac';
import {createApiQuery} from './queryUtils';

const CONCEPTS_TAG = 'concepts';

export const queryConcept = createApiQuery(ConceptsService.getConcept, CONCEPTS_TAG);
export const queryConcepts = createApiQuery(ConceptsService.getConcepts, CONCEPTS_TAG);
