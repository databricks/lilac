import { TasksService } from '$lilac';
import { createApiQuery } from './apiUtils';

const TASKS_TAG = 'tasks';

export const useGetTaskManifestQuery = createApiQuery(TasksService.getTaskManifest, TASKS_TAG);
