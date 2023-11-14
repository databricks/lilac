<script lang="ts">
  import type {CarbonIcon} from 'carbon-icons-svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  export let active = false;
  export let label: string;
  export let icon: typeof CarbonIcon | undefined = undefined;
  export let tooltip: string | undefined = undefined;
</script>

<button
  on:click
  use:hoverTooltip={{text: tooltip}}
  class="inline-flex items-center rounded-xl px-2 py-1 outline outline-1 outline-gray-500 focus:outline-1"
  class:active
>
  {#if icon != null}
    <div class="mr-2">
      <svelte:component this={icon} />
    </div>
  {/if}
  <div class="text-sm">{label}</div>
</button>

<style lang="postcss">
  .active {
    @apply bg-purple-200 outline-purple-700;
  }
</style>
