<script lang="ts">
  import {useGetTaskManifestQuery} from '$lib/store/apiServer';
  import {Loading, Popover} from 'carbon-components-svelte';
  import Checkmark from 'carbon-icons-svelte/lib/Checkmark.svelte';

  const tasks = useGetTaskManifestQuery();
  let showTasks = false;

  $: tasksList = Object.values($tasks.data?.tasks || {});

  $: runningTasks = tasksList.filter(task => task.status === 'pending');
  $: failedTasks = tasksList.filter(task => task.status === 'error');

  $: progress =
    runningTasks.reduce((acc, task) => acc + (task?.progress || 0), 0) / runningTasks.length;
</script>

<button
  class="relative border p-2 transition"
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
    on:click:outside={ev => {
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
