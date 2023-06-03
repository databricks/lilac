<script lang="ts">
  /**
   * Component that renders after a click of a string span. This component does both:
   *   1) Concept-specific accept or reject for each selected concept.
   *   2) Semantic similarity for computed embeddings.
   */

  import {fade} from 'svelte/transition';

  import {editConceptMutation} from '$lib/queries/conceptQueries';
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getComputedEmbeddings, getSearchEmbedding, getSearchPath} from '$lib/view_utils';
  import {serializePath} from '$lilac';
  import {Button} from 'carbon-components-svelte';
  import ThumbsDownFilled from 'carbon-icons-svelte/lib/ThumbsDownFilled.svelte';
  import ThumbsUpFilled from 'carbon-icons-svelte/lib/ThumbsUpFilled.svelte';
  import {createEventDispatcher} from 'svelte';
  import {clickOutside} from '../common/clickOutside';
  import EmbeddingBadge from './EmbeddingBadge.svelte';

  let datasetViewStore = getDatasetViewContext();
  let datasetStore = getDatasetContext();

  export let text: string;
  export let conceptName: string | null;
  export let conceptNamespace: string | null;
  // The coordinates of the click so we can position the popup next to the cursor.
  export let clickPosition: {x: number; y: number} | undefined;

  $: searchPath = getSearchPath($datasetViewStore, $datasetStore);

  const conceptEdit = editConceptMutation();
  const dispatch = createEventDispatcher();
  function addLabel(label: boolean) {
    if (!conceptName || !conceptNamespace)
      throw Error('Label could not be added, no active concept.');
    $conceptEdit.mutate([conceptNamespace, conceptName, {insert: [{text, label}]}]);
  }

  // Get the embeddings.
  const embeddings = queryEmbeddings();

  $: searchEmbedding = getSearchEmbedding(
    $datasetViewStore,
    $datasetStore,
    searchPath,
    ($embeddings.data || []).map(e => e.name)
  );

  $: computedEmbeddings = getComputedEmbeddings($datasetStore, searchPath);

  const findSimilar = (embedding: string) => {
    if (searchPath == null || searchEmbedding == null) return;

    datasetViewStore.addSearch({
      path: [serializePath(searchPath)],
      query: {
        type: 'semantic',
        search: text,
        embedding
      }
    });
  };
</script>

<div
  use:clickOutside={() => dispatch('close')}
  transition:fade={{duration: 60}}
  style={clickPosition != null ? `left: ${clickPosition.x}px; top: ${clickPosition.y}px` : ''}
  class="absolute z-10 inline-flex -translate-x-1/2 translate-y-6 flex-col gap-y-4 divide-gray-200 rounded border border-gray-200 bg-white p-1 shadow"
>
  {#if conceptName != null && conceptNamespace != null}
    <div class="flex flex-row px-4 pt-2">
      <span class="pr-4">{conceptName} / {conceptNamespace}</span>
      <button class="px-2" on:click={() => addLabel(true)}>
        <ThumbsUpFilled />
      </button>
      <button class="px-2" on:click={() => addLabel(false)}>
        <ThumbsDownFilled />
      </button>
    </div>
  {/if}

  <div class="more-button flex flex-col">
    {#each computedEmbeddings as computedEmbedding}
      <Button
        kind="ghost"
        class="w-full "
        size="small"
        on:click={() => findSimilar(computedEmbedding)}
        >Find similar <EmbeddingBadge class="hover:cursor-pointer" embedding={computedEmbedding} />
      </Button>
    {/each}
  </div>
</div>

<style lang="postcss">
  :global(.more-button .bx--btn) {
    @apply h-2 w-48;
  }
</style>
