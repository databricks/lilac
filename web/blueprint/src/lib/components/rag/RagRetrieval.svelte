<script context="module" lang="ts">
  export interface RagRetrievalResult {
    rowid: string;
    span: DataTypeCasted<'string_span'>;
    windowSpan: DataTypeCasted<'string_span'>;
    text: string;
    contextText: string;
    score: number;
    spanIndex: number;
    // All ordered chunk spans for the row, used for windowing.
    rowChunkSpans: DataTypeCasted<'string_span'>[];
  }
</script>

<script lang="ts">
  import {getRagRetrieval} from '$lib/queries/ragQueries';
  import {getRagViewContext} from '$lib/stores/ragViewStore';
  import type {DataTypeCasted, RagRetrievalResultItem} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import {createEventDispatcher} from 'svelte';
  import {colorFromScore} from '../datasetView/colors';

  export let retrievalResults: RagRetrievalResultItem[] | undefined = undefined;

  const ragViewStore = getRagViewContext();

  export let isFetching = false;

  const dispatch = createEventDispatcher();

  $: retrievalResultsQuery =
    $ragViewStore.datasetNamespace != null &&
    $ragViewStore.datasetName != null &&
    $ragViewStore.embedding != null &&
    $ragViewStore.query != null &&
    $ragViewStore.path != null &&
    $ragViewStore.topK != null &&
    $ragViewStore.windowSizeChunks != null
      ? getRagRetrieval({
          dataset_namespace: $ragViewStore.datasetNamespace,
          dataset_name: $ragViewStore.datasetName,
          embedding: $ragViewStore.embedding,
          query: $ragViewStore.query,
          path: $ragViewStore.path,
          chunk_window: $ragViewStore.windowSizeChunks,
          top_k: $ragViewStore.topK
        })
      : null;
  $: isFetching = $retrievalResultsQuery?.isFetching ?? false;
  $: retrievalResults = $retrievalResultsQuery?.data;

  $: {
    if ($retrievalResultsQuery?.data != null && !$retrievalResultsQuery?.isStale) {
      dispatch('results', $retrievalResultsQuery?.data);
    }
  }
</script>

<div class="mb-4 flex w-full flex-row justify-between">
  <div class="flex h-4 flex-row gap-x-4 font-normal">
    <div>
      <span class="mr-2">Chunk window</span>
      <input
        type="number"
        class="w-16 px-2"
        min="0"
        max="10"
        bind:value={$ragViewStore.windowSizeChunks}
      />
    </div>
    <div>
      <span class="mr-2">Top K</span>
      <input type="number" class="w-16 px-2" bind:value={$ragViewStore.topK} />
    </div>
  </div>
</div>
<div class="mb-8 h-full">
  {#if $retrievalResultsQuery?.isFetching}
    <SkeletonText lines={$ragViewStore.topK} />
  {/if}
  {#if $retrievalResultsQuery?.data != null}
    <div class="flex h-96 flex-col overflow-y-scroll">
      {#each $retrievalResultsQuery.data as retrievalResult}
        <!-- There is currently only one match span -->
        {@const windowSpan = retrievalResult.match_spans[0]}
        {@const prefix = retrievalResult.text.slice(0, windowSpan.start)}
        {@const suffix = retrievalResult.text.slice(windowSpan.end)}
        {@const matchedText = retrievalResult.text.slice(windowSpan.start, windowSpan.end)}
        <div class="flex flex-row gap-x-2 border-b border-b-neutral-200 py-2 text-sm">
          <div class="w-16">
            <span class="px-0.5" style:background-color={colorFromScore(retrievalResult.score)}
              >{retrievalResult.score.toFixed(2)}</span
            >
          </div>
          <div class="grow">
            <!-- Prefix context window -->
            {#if prefix != ''}
              <span class="whitespace-break-spaces">{prefix}</span>
            {/if}
            <!-- Retrieval chunk -->
            <span
              class="whitespace-break-spaces"
              style:background-color={colorFromScore(retrievalResult.score)}>{matchedText}</span
            >
            <!-- Suffix context window -->
            {#if suffix != ''}
              <span class="whitespace-break-spaces">{suffix}</span>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
