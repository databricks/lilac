import {TasksService} from '$lilac';
import {createApiMutation, createApiQuery} from './queryUtils';

export const TASKS_TAG = 'tasks';

export const queryTaskManifest = createApiQuery(TasksService.getTaskManifest, TASKS_TAG, {
  staleTime: 1000,
  refetchInterval: 1000,
  refetchIntervalInBackground: false,
  refetchOnWindowFocus: true
});

export const cancelTaskMutation = createApiMutation(TasksService.cancelTask);
