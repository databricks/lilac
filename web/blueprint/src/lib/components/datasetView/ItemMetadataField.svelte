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
  import EmbeddingBadge from './EmbeddingBadge.svelte';
  import SignalBadge from './SignalBadge.svelte';

  export let node: RenderNode;
</script>

<div class="flex w-full items-center">
  <div class="flex w-full items-center text-xs font-medium text-neutral-500" title={node.fieldName}>
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
    <span class="truncate font-mono">{node.fieldName}</span>
  </div>
  <div class="w-10">
    {#if node.isEmbeddingSignal}
      <EmbeddingBadge hideEmbeddingName={true} embedding={node.field.signal?.signal_name} />
    {:else if node.isSignal}
      <SignalBadge isPreview={node.isPreviewSignal} />
    {/if}
  </div>
  <div
    title={node.value?.toString()}
    class="w-full truncate text-right text-xs"
    class:italic={node.formattedValue === null}
  >
    {node.formattedValue}
  </div>
</div>

{#if node.children && node.expanded}
  <div transition:slide|local>
    {#each node.children as child (serializePath(child.path))}
      <div class="pl-2"><svelte:self node={child} /></div>
    {/each}
  </div>
{/if}
