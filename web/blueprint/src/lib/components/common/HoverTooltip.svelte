<script lang="ts">
  import type {SvelteComponent} from 'svelte';

  export let text: string | undefined;
  export let x: number;
  export let y: number;
  export let component: typeof SvelteComponent | undefined;
  export let props: Record<string, unknown> | undefined;
  const pageWidth = window.innerWidth;
  const marginPx = 10;

  let width = 0;
</script>

<div
  role="tooltip"
  class="absolute mt-2 min-w-max max-w-xs
    -translate-x-1/2 break-words border border-gray-300 bg-white p-2 shadow-md"
  style:top="{y}px"
  style:left="{Math.max(width / 2 + marginPx, Math.min(x, pageWidth - width / 2 - marginPx))}px"
  bind:clientWidth={width}
>
  {#if text}
    <span class="whitespace-pre-wrap">{text}</span>
  {:else if component}
    <svelte:component this={component} {...props} />
  {/if}
</div>

<style>
  [role='tooltip'] {
    z-index: 10000;
  }
</style>
