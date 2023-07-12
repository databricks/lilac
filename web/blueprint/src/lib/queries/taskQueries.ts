import {TasksService} from '$lilac';
import {createApiQuery} from './queryUtils';

export const TASKS_TAG = 'tasks';

export const queryTaskManifest = createApiQuery(TasksService.getTaskManifest, TASKS_TAG, {
  staleTime: 500,
  refetchInterval: 500,
  refetchIntervalInBackground: false,
  refetchOnWindowFocus: true
});
