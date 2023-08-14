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

  import type {Notification} from '$lib/stores/notificationsStore';
  import {conceptIdentifier} from '$lib/utils';
  import ThumbsDownFilled from 'carbon-icons-svelte/lib/ThumbsDownFilled.svelte';
  import ThumbsUpFilled from 'carbon-icons-svelte/lib/ThumbsUpFilled.svelte';
  import {createEventDispatcher} from 'svelte';
  import {clickOutside} from '../common/clickOutside';
  import EmbeddingBadge from './EmbeddingBadge.svelte';

  export let details: SpanDetails;
  // The coordinates of the click so we can position the popup next to the cursor.
  export let clickPosition: {x: number; y: number} | undefined;

  export let embeddings: string[];

  // We cant create mutations from this component since it is hoisted so we pass the function in.
  export let addConceptLabel: (
    conceptName: string,
    conceptNamespace: string,
    text: string,
    label: boolean
  ) => void;
  export let findSimilar: ((embedding: string, text: string) => unknown) | null;
  export let addNotification: (notification: Notification) => void;

  const dispatch = createEventDispatcher();
  function addLabel(label: boolean) {
    if (!details.conceptName || !details.conceptNamespace)
      throw Error('Label could not be added, no active concept.');
    addConceptLabel(details.conceptNamespace, details.conceptName, details.text, label);
    const labelText = label === true ? 'Positive' : 'Negative';
    addNotification({
      kind: 'success',
      title: `[${labelText}] Concept label added`,
      subtitle: conceptIdentifier(details.conceptNamespace, details.conceptName),
      message: details.text
    });
    dispatch('click');
  }
</script>

<div
  use:clickOutside={() => dispatch('close')}
  transition:fade={{duration: 60}}
  style={clickPosition != null ? `left: ${clickPosition.x}px; top: ${clickPosition.y}px` : ''}
  class="absolute z-10 inline-flex -translate-x-1/2 translate-y-6 flex-col divide-y divide-gray-200 rounded border border-gray-200 bg-white shadow"
>
  {#if details.conceptName != null && details.conceptNamespace != null}
    <div class="flex flex-row items-center justify-between gap-x-4 p-2">
      <div class="flex-grow">{details.conceptNamespace} / {details.conceptName}</div>
      <div class="shrink-0">
        <button class="p-1" on:click={() => addLabel(true)}>
          <ThumbsUpFilled />
        </button>
        <button class="p-1" on:click={() => addLabel(false)}>
          <ThumbsDownFilled />
        </button>
      </div>
    </div>
  {/if}

  {#if findSimilar != null}
    <div class="more-button flex flex-col">
      {#each embeddings as computedEmbedding (computedEmbedding)}
        <button
          class="flex w-full items-center justify-between"
          on:click={() => {
            if (findSimilar) findSimilar(computedEmbedding, details.text);
            dispatch('click');
          }}
          ><div>Find similar</div>
          <EmbeddingBadge class="hover:cursor-pointer" embedding={computedEmbedding} />
        </button>
      {/each}
    </div>
  {/if}
</div>
