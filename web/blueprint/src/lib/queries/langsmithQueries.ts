import {LangsmithService} from '$lilac';
import {createApiQuery} from './queryUtils';

const LANGSMITH_TAG = 'langsmith';
export const queryDatasets = createApiQuery(LangsmithService.getDatasets, LANGSMITH_TAG, {});
