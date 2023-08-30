<script lang="ts">
  import type {Example} from '$lilac';
  import {TextInput} from 'carbon-components-svelte';
  import TrashCan from 'carbon-icons-svelte/lib/TrashCan.svelte';
  import {createEventDispatcher} from 'svelte';
  import {hoverTooltip} from '../common/HoverTooltip';

  export let data: Example[];
  export let canEditConcept: boolean;

  let newSampleText: string;

  const dispatch = createEventDispatcher();
</script>

<div class="">
  <TextInput
    bind:value={newSampleText}
    labelText="Add example"
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
      <span class="shrink">
        {row.text}
      </span>
      <div
        use:hoverTooltip={{
          text: !canEditConcept ? 'User does not have access to edit this concept.' : ''
        }}
        class:opacity-40={!canEditConcept}
      >
        <button
          title="Remove sample"
          class="shrink-0 opacity-50 hover:text-red-400 hover:opacity-100"
          on:click={() => dispatch('remove', row.id)}
          disabled={!canEditConcept}
        >
          <TrashCan size={16} />
        </button>
      </div>
    </div>
  {/each}
</div>
