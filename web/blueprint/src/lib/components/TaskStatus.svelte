<script lang="ts">
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {cancelTaskMutation, queryTaskManifest} from '$lib/queries/taskQueries';
  import {Loading, Modal, Popover, ProgressBar} from 'carbon-components-svelte';
  import type {ProgressBarProps} from 'carbon-components-svelte/types/ProgressBar/ProgressBar.svelte';
  import {CloseFilled} from 'carbon-icons-svelte';
  import Checkmark from 'carbon-icons-svelte/lib/Checkmark.svelte';
  import {hoverTooltip} from './common/HoverTooltip';

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

  const cancelTask = cancelTaskMutation();
  let cancelTaskId: string | undefined = undefined;
  let cancelTaskName: string | undefined = undefined;
  function cancelTaskAccepted() {
    if (cancelTaskId == null) return;
    $cancelTask.mutate([cancelTaskId]);
    cancelTaskId = undefined;
  }

  const authInfo = queryAuthInfo();
  $: canRunTasks =
    $authInfo.data?.access.dataset.compute_signals || $authInfo.data?.access.create_dataset;
</script>

{#if canRunTasks}
  <div
    use:hoverTooltip={{
      text: !canRunTasks ? 'User does not have access to run tasks.' : ''
    }}
  >
    <button
      disabled={!canRunTasks}
      class="task-button relative h-8 rounded border p-2 transition"
      class:opacity-40={!canRunTasks}
      on:click|stopPropagation={() => (showTasks = !showTasks)}
      class:bg-white={!runningTasks.length}
      class:bg-blue-200={runningTasks.length}
      class:border-blue-400={runningTasks.length}
    >
      <div class="relative z-10 flex gap-x-2 truncate">
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
            {@const progressValue =
              task.total_progress != null && task.total_len != null
                ? task.total_progress / task.total_len
                : undefined}
            {@const message = task.error ?? task.message}
            <div class="relative border-b-2 border-slate-200 p-4 text-left last:border-b-0">
              <div class="text-s flex flex-row items-center">
                <div class="mr-2">{task.name}</div>
                {#if task.status === 'pending'}
                  <div use:hoverTooltip={{text: 'Cancel task'}}>
                    <button
                      on:click|stopPropagation={() => {
                        cancelTaskId = id;
                        cancelTaskName = task.name;
                      }}><CloseFilled /></button
                    >
                  </div>
                {/if}
              </div>
              <div class="progress-container mt-3">
                <ProgressBar
                  labelText={message || ''}
                  helperText={task.status != 'completed' ? task.details || undefined : ''}
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
  </div>
{/if}

<Modal
  size="xs"
  open={cancelTaskId != null}
  modalHeading="Cancel task"
  primaryButtonText="Confirm"
  secondaryButtonText="Cancel"
  selectorPrimaryFocus=".bx--btn--primary"
  on:submit={() => cancelTaskAccepted()}
  on:click:button--secondary={() => {
    cancelTaskId = undefined;
  }}
  on:close={(cancelTaskId = undefined)}
>
  <div class="italic">
    {cancelTaskName}
  </div>
  <p class="mt-4">Are you sure you want to cancel this task?</p>
</Modal>

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
