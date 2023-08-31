import {LangsmithService} from '$lilac';
import {createApiQuery} from './queryUtils';

const TAG = 'langsmith';
export const queryDatasets = createApiQuery(LangsmithService.getDatasets, TAG, {});
