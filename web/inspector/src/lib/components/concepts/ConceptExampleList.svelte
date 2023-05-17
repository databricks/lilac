<script lang="ts">
  import type {Example} from '$lilac';
  import {TextInput} from 'carbon-components-svelte';
  import TrashCan from 'carbon-icons-svelte/lib/TrashCan.svelte';
  import {createEventDispatcher} from 'svelte';

  export let data: Example[];

  let newSampleText: string;

  const dispatch = createEventDispatcher();
</script>

<div class="">
  <TextInput
    bind:value={newSampleText}
    labelText="Add Sample"
    on:keydown={ev => {
      if (ev.key === 'Enter') {
        dispatch('add', newSampleText);
        newSampleText = '';
      }
    }}
  />
</div>
<div class="flex h-full w-full flex-col overflow-y-auto overflow-x-clip border border-gray-200">
  {#each [...data].reverse() as row}
    <div class="flex w-full justify-between gap-x-2 border-b border-gray-200 p-2 hover:bg-gray-50">
      <span class="shrink break-all">
        {row.text}
      </span>
      <button
        title="Remove sample"
        class="shrink-0 opacity-50 hover:text-red-400 hover:opacity-100"
        on:click={() => dispatch('remove', row.id)}
      >
        <TrashCan size={16} />
      </button>
    </div>
  {/each}
</div>
