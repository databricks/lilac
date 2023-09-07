<script lang="ts">
  import {goto} from '$app/navigation';
  import {querySelectRows} from '$lib/queries/datasetQueries';
  import {defaultDatasetViewState} from '$lib/stores/datasetViewStore';
  import {datasetLink} from '$lib/utils';
  import {getSpanValuePaths} from '$lib/view_utils';
  import {
    L,
    formatValue,
    getField,
    valueAtPath,
    type LilacSchema,
    type LilacValueNode,
    type Path
  } from '$lilac';
  import {Button, SkeletonText} from 'carbon-components-svelte';
  import {ArrowUpRight} from 'carbon-icons-svelte';
  import StringSpanHighlight from '../StringSpanHighlight.svelte';

  export let schema: LilacSchema;
  export let namespace: string;
  export let datasetName: string;
  export let mediaPath: Path;
  export let scorePath: Path;

  const NUM_ITEMS = 5;

  $: topRows = querySelectRows(
    namespace,
    datasetName,
    {
      columns: [mediaPath, scorePath],
      limit: NUM_ITEMS,
      combine_columns: true,
      sort_by: [scorePath]
    },
    schema
  );
  $: visibleFields = [getField(schema, scorePath)!];
  $: spanValuePaths = getSpanValuePaths(schema, visibleFields);

  function getText(row: LilacValueNode): string {
    return L.value(valueAtPath(row, mediaPath)!, 'string')!;
  }

  function getMaxScore(row: LilacValueNode): number {
    const scoresPath = scorePath.slice(0, scorePath.length - 2);
    const scoreNodes = valueAtPath(row, scoresPath) as unknown as LilacValueNode[];
    let maxScore = 0;
    for (const scoreNode of scoreNodes) {
      const score = L.value(valueAtPath(scoreNode, ['score'])!, 'float32')!;
      maxScore = Math.max(maxScore, score);
    }
    return maxScore;
  }

  function openDataset() {
    const datasetState = defaultDatasetViewState(namespace, datasetName);
    datasetState.query.sort_by = [scorePath];
    datasetState.query.sort_order = 'DESC';
    datasetState.insightsOpen = false;
    goto(datasetLink(namespace, datasetName, datasetState));
  }
</script>

{#if $topRows.isFetching}
  <SkeletonText />
{:else if $topRows.data}
  <div class="flex flex-col gap-y-4">
    <div class="flex h-8 justify-between text-lg">
      <div>Items with highest score</div>
      <div>
        <Button
          size="small"
          tooltipPosition="left"
          icon={ArrowUpRight}
          iconDescription={'Sort dataset by concept score'}
          on:click={openDataset}
        />
      </div>
    </div>
    {#each $topRows.data.rows as row}
      {@const text = getText(row)}
      {@const maxScore = getMaxScore(row)}
      <div class="flex gap-x-4 rounded border border-gray-300 px-4 py-2">
        <div class="flex-grow">
          <StringSpanHighlight
            {text}
            {row}
            spanPaths={spanValuePaths.spanPaths}
            valuePaths={spanValuePaths.valuePaths}
            embeddings={[]}
          />
        </div>
        <div class="flex flex-none flex-col items-end">
          <div class="text-sm text-gray-500">Max score</div>
          <div class="text-lg">{formatValue(maxScore)}</div>
        </div>
      </div>
    {/each}
  </div>
{/if}
