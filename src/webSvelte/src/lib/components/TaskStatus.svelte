<script lang="ts">
  import { useGetTaskManifestQuery } from '$lib/store/apiServer';
  import { Popover } from 'carbon-components-svelte';
  import Checkmark from 'carbon-icons-svelte/lib/Checkmark.svelte';

  const tasks = useGetTaskManifestQuery();
  let showTasks = false;

  $: tasksList = Object.values($tasks.data?.tasks || {});

  $: runningTasks = tasksList.filter((task) => task.status === 'pending');
  $: finishedTasks = tasksList.filter((task) => task.status === 'completed');
  $: failedTasks = tasksList.filter((task) => task.status === 'error');

</script>

<button
  class="relative flex gap-x-2 border p-2 transition"
  on:click|stopPropagation={() => (showTasks = !showTasks)}
  class:bg-green-300={runningTasks.length}
>
  {#if !runningTasks.length}
    Tasks <Checkmark />
  {:else if runningTasks.length === 1}
    1 Runnning task
    {#if runningTasks[0].progress !== undefined}
      ({(runningTasks[0].progress * 100).toFixed(0)}%)
    {/if}
  {:else}
    {runningTasks.length} running tasks...
  {/if}

  <Popover
    on:click:outside={(ev) => {
      if (showTasks) showTasks = false;
    }}
    align="bottom-right"
    caret
    closeOnOutsideClick
    open={showTasks}
  >
    <div class="flex flex-col">
      {#each tasksList as task}
        <div class="p-4 text-left">
          {task.name} - {task.status}
        </div>
      {/each}
    </div>
  </Popover>
</button>
