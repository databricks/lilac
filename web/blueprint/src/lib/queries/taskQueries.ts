import {TasksService} from '$lilac';
import {createApiQuery} from './queryUtils';

export const TASKS_TAG = 'tasks';

export const queryTaskManifest = createApiQuery(TasksService.getTaskManifest, TASKS_TAG, {
  staleTime: 1000,
  refetchInterval: 1000,
  refetchIntervalInBackground: false,
  refetchOnWindowFocus: true
});
