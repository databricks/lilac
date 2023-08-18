<script lang="ts">
  import {goto} from '$app/navigation';
  import Page from '$lib/components/Page.svelte';
  import {queryTaskManifest} from '$lib/queries/taskQueries';
  import {getUrlHashContext} from '$lib/stores/urlHashStore';
  import {datasetLink} from '$lib/utils';
  import {Button, ProgressBar, ToastNotification} from 'carbon-components-svelte';
  import type {ProgressBarProps} from 'carbon-components-svelte/types/ProgressBar/ProgressBar.svelte';
  import {ArrowUpRight} from 'carbon-icons-svelte';

  let namespace: string;
  let datasetName: string;
  let loadingTaskId: string;

  const urlHashStore = getUrlHashContext();

  $: {
    if ($urlHashStore.page === 'datasets/loading' && $urlHashStore.identifier != null) {
      [namespace, datasetName, loadingTaskId] = $urlHashStore.identifier.split('/');
    }
  }

  const tasks = queryTaskManifest();

  $: task = loadingTaskId != null && $tasks.data != null ? $tasks.data.tasks[loadingTaskId] : null;
  $: progressValue = task?.step_progress == null ? undefined : task.step_progress;

  const taskToProgressStatus: {[taskStatus: string]: ProgressBarProps['status']} = {
    pending: 'active',
    completed: 'finished',
    error: 'error'
  };
</script>

<Page>
  <div class="w-full p-8">
    {#if $tasks.isSuccess && task == null}
      <ToastNotification
        hideCloseButton
        kind="warning"
        fullWidth
        lowContrast
        title="Unknown task"
        caption="This could be from a stale link, or a new server instance."
      />
    {/if}
    {#if task}
      <h3>
        {#if task.status == 'pending'}
          Loading {namespace}/{datasetName}...
        {:else if task.status === 'completed'}
          Done loading {namespace}/{datasetName}
        {:else if task.status === 'error'}
          Error loading {namespace}/{datasetName}
        {/if}
      </h3>
      {#if task.status != 'error'}
        <div class="mt-6">
          <ProgressBar
            labelText={task.message || ''}
            helperText={task.status != 'completed' ? task.details : ''}
            value={task.status === 'completed' ? 1.0 : progressValue}
            max={1.0}
            status={taskToProgressStatus[task.status]}
          />
        </div>
      {/if}

      {#if task.status == 'completed'}
        <div class="dataset-link mt-8">
          <Button
            size="xl"
            icon={ArrowUpRight}
            iconDescription={'Open dataset'}
            on:click={() => goto(datasetLink(namespace, datasetName))}>Open dataset</Button
          >
        </div>
      {:else if task.status === 'error'}
        <ToastNotification
          hideCloseButton
          kind="error"
          fullWidth
          lowContrast
          title="Error loading dataset"
          caption={task.error}
        />
      {/if}
    {/if}
  </div>
</Page>

<style lang="postcss">
  :global(.dataset-link .bx--btn.bx--btn--primary) {
    @apply flex h-16 min-h-0 flex-row items-center justify-items-center py-6 text-base;
  }
</style>
