<script lang="ts">
  import {queryDatasetStats} from '$lib/queries/datasetQueries';
  import {formatValue, type LilacField, type LilacSchema, type Path} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import ConceptInsight from './ConceptInsight.svelte';

  export let concepts: LilacField[];
  export let mediaPath: Path;
  export let schema: LilacSchema;
  export let namespace: string;
  export let datasetName: string;

  $: statsQuery = queryDatasetStats(namespace, datasetName, {leaf_path: mediaPath});
  $: avgTextLength = $statsQuery.data?.avg_text_length;
  $: totalCount = $statsQuery.data?.total_count;
</script>

<div class="relative flex flex-col gap-y-4">
  <div
    class="sticky top-0 flex rounded-xl border border-gray-300 bg-slate-50/80 px-4 py-3 backdrop-blur-sm"
  >
    <div class="flex-grow text-2xl font-semibold text-slate-900">{mediaPath}</div>
    <div class="flex-none text-sm text-gray-500">
      {#if totalCount && avgTextLength}
        <div>{formatValue(totalCount)} items</div>
        <div>{avgTextLength} chars on average</div>
      {:else}
        <SkeletonText paragraph lines={2} width="200px" />
      {/if}
    </div>
  </div>
  {#each concepts as concept}
    <ConceptInsight {schema} {namespace} {datasetName} field={concept} />
  {/each}
</div>
