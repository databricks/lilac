import {DATASETS_TAG} from '$lib/queries/datasetQueries';
import {queryClient} from '$lib/queries/queryClient';
import type {TaskInfo, TaskManifest} from '$lilac';
import {writable} from 'svelte/store';

const store = writable({
  taskStatus: new Map<string, TaskInfo>(),
  taskCallbacks: new Map<string, Array<(task: TaskInfo) => void>>()
});

/**
 * Watch a task for completion or error.
 */
export function watchTask(taskid: string, onDone: (task: TaskInfo) => void) {
  store.update(state => {
    const currentCallbacks = state.taskCallbacks.get(taskid) || [];
    state.taskCallbacks.set(taskid, [...currentCallbacks, onDone]);
    return state;
  });
}

/**
 * Update the monitored tasks with a new task manifest.
 */
export function onTasksUpdate(taskManifest: TaskManifest) {
  store.update(state => {
    for (const [taskId, task] of Object.entries(taskManifest.tasks)) {
      if (state.taskStatus.get(taskId)?.status != task.status) {
        if (task.type === 'dataset_load') {
          queryClient.invalidateQueries([DATASETS_TAG]);
        }
      }
      state.taskStatus.set(taskId, task);
    }

    for (const taskid of state.taskCallbacks.keys()) {
      const task = taskManifest.tasks[taskid];
      if (task?.status == 'error' || task.status === 'completed') {
        const taskCallbacks = state.taskCallbacks.get(taskid) || [];
        while (taskCallbacks.length) {
          taskCallbacks.pop()?.(task);
        }
        state.taskCallbacks.delete(taskid);
      }
    }
    return state;
  });
}
