<script lang="ts">
  import type {SvelteComponent} from 'svelte';

  export let tooltipText: string | undefined;
  export let x: number;
  export let y: number;
  export let tooltipBodyComponent: typeof SvelteComponent | undefined;
  export let tooltipBodyProps: Record<string, unknown> | undefined;
  const pageWidth = window.innerWidth;
  const marginPx = 10;

  let width = 0;
</script>

<div
  role="tooltip"
  class="absolute mt-2 min-w-max max-w-xs -translate-x-1/2 break-words
    border border-gray-300 bg-white p-2 shadow-md"
  style:top="{y}px"
  style:left="{Math.max(width / 2 + marginPx, Math.min(x, pageWidth - width / 2 - marginPx))}px"
  bind:clientWidth={width}
>
  {#if tooltipText}
    <span class="whitespace-pre-wrap">{tooltipText}</span>
  {:else if tooltipBodyComponent}
    <svelte:component this={tooltipBodyComponent} {...tooltipBodyProps} />
  {/if}
</div>
