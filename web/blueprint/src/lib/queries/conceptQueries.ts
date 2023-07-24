import {ConceptsService} from '$lilac';
import {DATASETS_TAG} from './datasetQueries';
import {queryClient} from './queryClient';
import {createApiMutation, createApiQuery} from './queryUtils';

export const CONCEPTS_TAG = 'concepts';

export const queryConcept = createApiQuery(ConceptsService.getConcept, CONCEPTS_TAG);
export const queryConcepts = createApiQuery(ConceptsService.getConcepts, CONCEPTS_TAG);
export const queryConceptModels = createApiQuery(ConceptsService.getConceptModels, CONCEPTS_TAG);
export const conceptModelMutation = createApiMutation(ConceptsService.getConceptModel, {
  onSuccess: () => {
    queryClient.invalidateQueries([CONCEPTS_TAG]);
  }
});
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

export const deleteConceptMutation = createApiMutation(ConceptsService.deleteConcept, {
  onSuccess: () => queryClient.invalidateQueries([CONCEPTS_TAG])
});

export const queryConceptScore = createApiQuery(ConceptsService.score, CONCEPTS_TAG);

export const queryConceptColumnInfos = createApiQuery(
  ConceptsService.getConceptColumnInfos,
  CONCEPTS_TAG
);
