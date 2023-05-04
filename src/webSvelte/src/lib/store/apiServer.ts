import { TasksService } from '../fastapi_client';
import { createApiQuery } from './apiUtils';

const TASKS_TAG = 'tasks';

export const useGetTaskManifestQuery = createApiQuery(TasksService.getTaskManifest, TASKS_TAG);
