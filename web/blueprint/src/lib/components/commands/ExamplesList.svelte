<script lang="ts">
  import {TextInput} from 'carbon-components-svelte';
  import {Close} from 'carbon-icons-svelte';
  import {hoverTooltip} from '../common/HoverTooltip';

  export let examples: string[];
</script>

<div class="flex flex-col gap-y-2">
  <div class="flex flex-col gap-y-2">
    {#each examples as _, i}
      <div class="flex flex-row items-center gap-x-2">
        <div class="shrink-0 text-base">{i + 1}</div>
        <div class="grow">
          <TextInput bind:value={examples[i]} />
        </div>
        <div>
          <button
            class="px-1 py-2"
            use:hoverTooltip={{text: 'Remove example'}}
            on:click={() => {
              examples.splice(i, 1);
              examples = examples;
            }}
          >
            <Close />
          </button>
        </div>
      </div>
    {/each}
  </div>
  <div>
    <button
      class="bg-slate-600 p-2 text-white hover:bg-slate-400"
      class:ml-8={examples?.length > 0}
      on:click={() => {
        examples = [...(examples || []), ''];
      }}
    >
      + Add
    </button>
  </div>
</div>
