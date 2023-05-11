import {TasksService} from '$lilac';
import {createApiQuery} from './queryUtils';

export const TASKS_TAG = 'tasks';

export const queryTaskManifest = createApiQuery(TasksService.getTaskManifest, TASKS_TAG, {
  staleTime: 3000,
  refetchInterval: 3000,
  refetchIntervalInBackground: false,
  refetchOnWindowFocus: true
});
