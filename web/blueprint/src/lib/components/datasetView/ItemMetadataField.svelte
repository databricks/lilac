<script context="module" lang="ts">
  export interface RenderNode {
    field: LilacField;
    path: Path;
    fieldName: string;
    expanded: boolean;
    children?: RenderNode[];
    isSignal: boolean;
    isPreviewSignal: boolean;
    isEmbeddingSignal: boolean;
    value?: DataTypeCasted | null;
    formattedValue?: string | null;
  }
</script>

<script lang="ts">
  import {serializePath, type DataTypeCasted, type LilacField, type Path} from '$lilac';
  import {ChevronDown, ChevronUp} from 'carbon-icons-svelte';
  import {slide} from 'svelte/transition';

  export let node: RenderNode;
</script>

<div
  class="flex items-center pr-2"
  class:bg-blue-100={node.isSignal}
  class:bg-emerald-100={node.isPreviewSignal}
  style:padding-left={0.25 + (node.path.length - 1) * 0.5 + 'rem'}
>
  <div
    class="contents flex-grow items-center text-xs font-medium text-neutral-500"
    title={node.fieldName}
  >
    <button
      class="p-1"
      class:invisible={!node.children?.length}
      on:click={() => {
        node.expanded = !node.expanded;
        node = node;
      }}
    >
      {#if node.expanded}
        <ChevronUp />
      {:else}
        <ChevronDown />
      {/if}
    </button>
    <div class="truncated truncate font-mono">{node.fieldName}</div>
  </div>
  <div
    title={node.value?.toString()}
    class="truncated flex-grow truncate text-right text-xs"
    class:italic={node.formattedValue === null}
  >
    {node.formattedValue}
  </div>
</div>

{#if node.children && node.expanded}
  <div
    transition:slide|local
    class:bg-blue-100={node.isSignal}
    class:bg-emerald-100={node.isPreviewSignal}
  >
    {#each node.children as child (serializePath(child.path))}
      <svelte:self node={child} />
    {/each}
  </div>
{/if}

<style lang="postcss">
  .truncated {
    min-width: 5ch;
  }
</style>
