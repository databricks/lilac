import {ConceptsService} from '$lilac';
import {DATASETS_TAG} from './datasetQueries';
import {queryClient} from './queryClient';
import {createApiMutation, createApiQuery} from './queryUtils';

const CONCEPTS_TAG = 'concepts';

export const queryConcept = createApiQuery(ConceptsService.getConcept, CONCEPTS_TAG);
export const queryConcepts = createApiQuery(ConceptsService.getConcepts, CONCEPTS_TAG);

export const createConceptMutation = createApiMutation(ConceptsService.createConcept, {
  onSuccess: () => {
    queryClient.invalidateQueries([CONCEPTS_TAG]);
  }
});

export const editConceptMutation = createApiMutation(ConceptsService.editConcept, {
  onSuccess: () => {
    queryClient.invalidateQueries([CONCEPTS_TAG]);
    // Invalidate selected rows because the concept may have changed
    queryClient.invalidateQueries([DATASETS_TAG, 'selectRows']);
  }
});
