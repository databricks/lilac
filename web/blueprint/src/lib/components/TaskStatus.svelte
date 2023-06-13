<script lang="ts">
  import {queryTaskManifest} from '$lib/queries/taskQueries';
  import {Loading, Popover, ProgressBar} from 'carbon-components-svelte';
  import type {ProgressBarProps} from 'carbon-components-svelte/types/ProgressBar/ProgressBar.svelte';
  import Checkmark from 'carbon-icons-svelte/lib/Checkmark.svelte';

  const tasks = queryTaskManifest();
  let showTasks = false;

  $: tasksList = Object.entries($tasks.data?.tasks || {}).sort(
    ([, task1], [, task2]) => Date.parse(task2.start_timestamp) - Date.parse(task1.start_timestamp)
  );

  $: runningTasks = tasksList.filter(([, task]) => task.status === 'pending');
  $: failedTasks = tasksList.filter(([, task]) => task.status === 'error');

  $: progress = $tasks.data?.progress || 0.0;

  const taskToProgressStatus: {[taskStatus: string]: ProgressBarProps['status']} = {
    pending: 'active',
    completed: 'finished',
    error: 'error'
  };
</script>

<button
  class="task-button relative rounded border p-2 transition"
  on:click|stopPropagation={() => (showTasks = !showTasks)}
  class:bg-white={!runningTasks.length}
  class:bg-blue-200={runningTasks.length}
  class:border-blue-400={runningTasks.length}
>
  <div class="relative z-10 flex gap-x-2">
    {#if runningTasks.length}
      {runningTasks.length} running task{runningTasks.length > 1 ? 's' : ''}... <Loading
        withOverlay={false}
        small
      />
    {:else if failedTasks.length}
      {failedTasks.length} failed task{failedTasks.length > 1 ? 's' : ''}
    {:else}
      Tasks <Checkmark />
    {/if}
  </div>
  {#if runningTasks.length === 1}
    <div
      class="absolute left-0 top-0 z-0 h-full bg-blue-400 transition"
      style:width="{progress * 100}%"
    />
  {/if}

  <Popover
    on:click:outside={() => {
      if (showTasks) showTasks = false;
    }}
    align="bottom-right"
    caret
    closeOnOutsideClick
    open={showTasks}
  >
    <div class="flex flex-col">
      {#each tasksList as [id, task] (id)}
        {@const progressValue = task.step_progress == null ? undefined : task.step_progress}
        <div class="relative border-b-2 border-slate-200 p-4 text-left last:border-b-0">
          <div class="text-s flex flex-row">
            <div class="mr-2">{task.name}</div>
          </div>
          <div class="progress-container mt-3">
            <ProgressBar
              labelText={task.message || ''}
              helperText={task.status != 'completed' ? task.details : ''}
              value={task.status === 'completed' ? 1.0 : progressValue}
              max={1.0}
              size={'sm'}
              status={taskToProgressStatus[task.status]}
            />
          </div>
        </div>
      {/each}
    </div>
  </Popover>
</button>

<style lang="postcss">
  :global(.progress-container .bx--progress-bar__label) {
    @apply text-xs;
    @apply font-light;
  }
  :global(.progress-container .bx--progress-bar__helper-text) {
    @apply text-xs;
    @apply font-light;
  }
  :global(.task-button .bx--popover-contents) {
    width: 28rem;
    max-width: 28rem;
  }
</style>
