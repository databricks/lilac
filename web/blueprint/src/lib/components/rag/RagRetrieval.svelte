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
  import {querySelectRows, querySelectRowsSchema} from '$lib/queries/datasetQueries';
  import {getRagViewContext} from '$lib/stores/ragViewStore';
  import type {DataTypeCasted, LilacValueNode, SelectRowsOptions, SemanticSearch} from '$lilac';
  import {L, ROWID, childFields, valueAtPath} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import {createEventDispatcher} from 'svelte';
  import {colorFromScore} from '../datasetView/colors';

  export let retrievalResults: RagRetrievalResult[] | undefined = undefined;

  const ragViewStore = getRagViewContext();

  export let isFetching = false;

  const dispatch = createEventDispatcher();

  $: semanticSearch = {
    path: $ragViewStore.path,
    query: $ragViewStore.query,
    query_type: 'question',
    embedding: $ragViewStore.embedding,
    type: 'semantic'
  } as SemanticSearch;

  let selectRowsOptions: SelectRowsOptions | null = null;
  $: {
    if ($ragViewStore.path && $ragViewStore.embedding && $ragViewStore.query != null) {
      selectRowsOptions = {
        columns: [ROWID, $ragViewStore.path],
        limit: $ragViewStore.topK,
        combine_columns: true,
        searches: [semanticSearch]
      };
    }
  }
  // TODO: nsthorat, this causes invalidation a lot because searches contains the text of the query.
  $: selectRowsSchema =
    selectRowsOptions && $ragViewStore.datasetNamespace && $ragViewStore.datasetName
      ? querySelectRowsSchema($ragViewStore.datasetNamespace, $ragViewStore.datasetName, {
          columns: selectRowsOptions.columns,
          searches: selectRowsOptions.searches,
          combine_columns: selectRowsOptions.combine_columns
        })
      : null;
  $: topRows =
    selectRowsOptions != null &&
    $ragViewStore.datasetNamespace != null &&
    $ragViewStore.datasetName != null &&
    $selectRowsSchema?.data != null
      ? querySelectRows(
          $ragViewStore.datasetNamespace,
          $ragViewStore.datasetName,
          selectRowsOptions,
          $selectRowsSchema.data.schema
        )
      : null;

  $: isFetching = $topRows?.isFetching || $selectRowsSchema?.isFetching || false;
  $: {
    if (isFetching) {
      retrievalResults = undefined;
    }
  }

  $: semanticSimilarityField =
    $selectRowsSchema?.data != null
      ? childFields($selectRowsSchema.data.schema).filter(
          f => f.signal != null && f.signal.signal_name === 'semantic_similarity'
        )[0]
      : null;

  $: {
    if (semanticSimilarityField != null && $ragViewStore.path != null && $topRows?.data != null) {
      retrievalResults = ($topRows.data?.rows || [])
        .flatMap(row => {
          const valueNodes = valueAtPath(
            row,
            semanticSimilarityField!.path
          )! as unknown as LilacValueNode[];
          if (valueNodes == null) {
            return [];
          }
          const text = L.value<'string'>(valueAtPath(row, $ragViewStore.path!)!)!;
          const retrievalResults: RagRetrievalResult[] = [];
          // The entire row span scores in order. Useful for increasing the window.
          const rowSpanScores: {
            span: DataTypeCasted<'string_span'>;
            score: number;
            text: string;
          }[] = [];
          for (const valueNode of valueNodes) {
            const span = L.span(valueNode)!;
            const score = L.value(valueAtPath(valueNode, ['score'])!, 'float32')!;
            rowSpanScores.push({span, score, text});
          }
          for (const [spanIndex, {span, score, text}] of rowSpanScores.entries()) {
            const startWindowChunk =
              rowSpanScores[Math.max(0, spanIndex - $ragViewStore.windowSizeChunks)].span;
            const endWindowChunk =
              rowSpanScores[
                Math.min(rowSpanScores.length - 1, spanIndex + $ragViewStore.windowSizeChunks)
              ].span;
            const contextText = text.slice(startWindowChunk?.start, endWindowChunk?.end) as string;
            retrievalResults.push({
              rowid: L.value<'string'>(valueAtPath(row, [ROWID])!)!,
              span,
              windowSpan: {start: startWindowChunk!.start, end: endWindowChunk!.end},
              text,
              contextText,
              score,
              spanIndex,
              rowChunkSpans: rowSpanScores.map(v => v.span)
            });
          }
          return retrievalResults;
        })
        .sort((a, b) => b.score - a.score)
        .slice(0, $ragViewStore.topK);
    }
  }
  $: dispatch('results', retrievalResults);
</script>

<div class="rag-section-header mb-4 flex w-full flex-row justify-between">
  <div>Retrieval</div>
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
  {#if $topRows?.isFetching}
    <SkeletonText lines={$ragViewStore.topK} />
  {/if}
  {#if retrievalResults != null}
    <div class="flex h-96 flex-col overflow-y-scroll">
      {#each retrievalResults as retrievalResult}
        {@const prefix = retrievalResult.text.slice(
          retrievalResult.windowSpan?.start,
          retrievalResult.span?.start
        )}
        {@const suffix = retrievalResult.text.slice(
          retrievalResult.span?.end,
          retrievalResult.windowSpan?.end
        )}
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
              style:background-color={colorFromScore(retrievalResult.score)}
              >{retrievalResult.text.slice(
                retrievalResult.span?.start,
                retrievalResult.span?.end
              )}</span
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
