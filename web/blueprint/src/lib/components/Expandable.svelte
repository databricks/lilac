<script lang="ts">
  import {ChevronDown, ChevronUp} from 'carbon-icons-svelte';

  export let expanded = false;
</script>

<div class="rounded-xl border border-gray-300">
  <button class="w-full p-4 text-left hover:bg-gray-200" on:click={() => (expanded = !expanded)}>
    <div class="flex items-center justify-between gap-x-3">
      <slot name="above" />
      {#if expanded}
        <ChevronUp />
      {:else}
        <ChevronDown />
      {/if}
    </div>
  </button>
  <div class="p-4" class:hidden={!expanded}><slot name="below" /></div>
</div>
