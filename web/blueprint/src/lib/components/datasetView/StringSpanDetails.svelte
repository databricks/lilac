<script lang="ts" context="module">
  /**
   * Component that renders after a click of a string span. This component does both:
   *   1) Concept-specific accept or reject for each selected concept.
   *   2) Semantic similarity for computed embeddings.
   */
  export interface SpanDetails {
    conceptName: string | null;
    conceptNamespace: string | null;
    text: string;
  }
</script>

<script lang="ts">
  import {fade} from 'svelte/transition';

  import {Button} from 'carbon-components-svelte';
  import ThumbsDownFilled from 'carbon-icons-svelte/lib/ThumbsDownFilled.svelte';
  import ThumbsUpFilled from 'carbon-icons-svelte/lib/ThumbsUpFilled.svelte';
  import {createEventDispatcher} from 'svelte';
  import {clickOutside} from '../common/clickOutside';
  import EmbeddingBadge from './EmbeddingBadge.svelte';

  export let details: SpanDetails;
  // The coordinates of the click so we can position the popup next to the cursor.
  export let clickPosition: {x: number; y: number} | undefined;

  export let computedEmbeddings: string[];

  // We cant create mutations from this component since it is hoisted so we pass the function in.
  export let addConceptLabel: (
    conceptName: string,
    conceptNamespace: string,
    text: string,
    label: boolean
  ) => void;
  export let findSimilar: (embedding: string, text: string) => unknown;

  const dispatch = createEventDispatcher();
  function addLabel(label: boolean) {
    if (!details.conceptName || !details.conceptNamespace)
      throw Error('Label could not be added, no active concept.');
    addConceptLabel(details.conceptNamespace, details.conceptName, details.text, label);
    dispatch('click');
  }
</script>

<div
  use:clickOutside={() => dispatch('close')}
  transition:fade={{duration: 60}}
  style={clickPosition != null ? `left: ${clickPosition.x}px; top: ${clickPosition.y}px` : ''}
  class="absolute z-10 inline-flex -translate-x-1/2 translate-y-6 flex-col gap-y-4 divide-gray-200 rounded border border-gray-200 bg-white p-1 shadow"
>
  {#if details.conceptName != null && details.conceptNamespace != null}
    <div class="flex flex-row px-4 pt-2">
      <span class="pr-4">{details.conceptNamespace} / {details.conceptName}</span>
      <button class="px-2" on:click={() => addLabel(true)}>
        <ThumbsUpFilled />
      </button>
      <button class="px-2" on:click={() => addLabel(false)}>
        <ThumbsDownFilled />
      </button>
    </div>
  {/if}

  <div class="more-button flex flex-col">
    {#each computedEmbeddings as computedEmbedding (computedEmbedding)}
      <Button
        kind="ghost"
        class="w-full"
        size="small"
        on:click={() => {
          findSimilar(computedEmbedding, details.text);
          dispatch('click');
        }}
        >Find similar <EmbeddingBadge class="hover:cursor-pointer" embedding={computedEmbedding} />
      </Button>
    {/each}
  </div>
</div>

<style lang="postcss">
  :global(.more-button .bx--btn) {
    @apply h-6 w-48;
  }
</style>
