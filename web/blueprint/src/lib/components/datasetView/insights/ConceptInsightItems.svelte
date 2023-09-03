<script lang="ts">
  import {querySelectRows} from '$lib/queries/datasetQueries';
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
  import {SkeletonText} from 'carbon-components-svelte';
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
  $: visibleFields = [
    getField(schema, mediaPath)!,
    getField(schema, scorePath.slice(0, scorePath.length - 2))!,
    getField(schema, scorePath.slice(0, scorePath.length - 1))!,
    getField(schema, scorePath)!
  ];
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
</script>

{#if $topRows.isFetching}
  <SkeletonText />
{:else if $topRows.data}
  <div class="flex flex-col gap-y-4">
    <div class="text-lg">Items with highest score</div>
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
          <div class="text-sm text-gray-500">Max. span score</div>
          <div class="text-lg">{formatValue(maxScore)}</div>
        </div>
      </div>
    {/each}
  </div>
{/if}
