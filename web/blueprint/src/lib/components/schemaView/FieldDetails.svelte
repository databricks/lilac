<script lang="ts">
  import {queryDatasetStats, querySelectGroups} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {formatValue, type BinaryFilter, type LeafValue, type LilacField} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import {Information} from 'carbon-icons-svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import Histogram from './Histogram.svelte';

  export let field: LilacField;

  const store = getDatasetViewContext();

  $: statsQuery = queryDatasetStats($store.namespace, $store.datasetName, {leaf_path: field.path});
  $: groupsQuery = querySelectGroups($store.namespace, $store.datasetName, {
    leaf_path: field.path,
    filters: $store.queryOptions.filters
  });

  $: counts =
    $groupsQuery.data != null ? ($groupsQuery.data.counts as [LeafValue, number][]) : null;
  $: stats = $statsQuery.data != null ? $statsQuery.data : null;

  $: bins =
    $groupsQuery.data != null
      ? ($groupsQuery.data.bins as [string, number | null, number | null][])
      : null;

  function rowClicked(value: LeafValue, index: number) {
    if (value == null) return;
    if (bins != null) {
      const [, min, max] = bins[index];
      if (min != null) {
        const filter: BinaryFilter = {path: field.path, op: 'greater_equal', value: min};
        store.addFilter(filter);
      }
      if (max != null) {
        const filter: BinaryFilter = {path: field.path, op: 'less', value: max};
        store.addFilter(filter);
      }
      return;
    }
    const filter: BinaryFilter = {path: field.path, op: 'equals', value};
    store.addFilter(filter);
  }
</script>

<div class="p-4">
  {#if $statsQuery.error}
    <p>Error: {$statsQuery.error.message}</p>
  {:else if stats == null}
    <!-- Loading... -->
    <SkeletonText paragraph width="50%" />
  {:else}
    <table class="stats-table w-full">
      <tbody>
        <tr>
          <td>
            <span use:hoverTooltip={{text: 'Total number of rows where the value is defined.'}}>
              <Information class="inline" />
            </span>
            <span>Total count</span>
          </td>
          <td>{formatValue(stats.total_count)}</td>
        </tr>
        <tr>
          <td>
            <span
              use:hoverTooltip={{text: 'An approximation of the total number of unique values.'}}
            >
              <Information class="inline" />
            </span>
            <span>Unique values</span>
          </td>
          <td>~{formatValue(stats.approx_count_distinct)}</td>
        </tr>
        {#if stats.avg_text_length}
          <tr>
            <td>
              <span use:hoverTooltip={{text: 'The average length of the text in characters.'}}>
                <Information class="inline" />
              </span>
              <span>Average text length</span>
            </td>
            <td>{formatValue(stats.avg_text_length)}</td>
          </tr>
        {/if}
        {#if stats.min_val && stats.max_val}
          <tr>
            <td>
              <span use:hoverTooltip={{text: 'The minimum and maximum value across the dataset'}}>
                <Information class="inline" />
              </span>
              <span>Range</span>
            </td>
            <td>{formatValue(stats.min_val)} .. {formatValue(stats.max_val)}</td>
          </tr>
        {/if}
      </tbody>
    </table>
  {/if}

  {#if $groupsQuery.error}
    <p>Error: {$groupsQuery.error.message}</p>
  {:else if counts == null}
    <!-- Loading... -->
    <SkeletonText paragraph width="50%" />
  {:else if counts.length > 0}
    <div class="mt-4">
      <Histogram
        {counts}
        {bins}
        {field}
        on:row-click={e => rowClicked(e.detail.value, e.detail.index)}
      />
    </div>
  {/if}
</div>

<style lang="postcss">
  .stats-table td {
    @apply w-48;
  }
  .stats-table td:first-child {
    @apply truncate py-2 pr-2;
  }
  .stats-table td:last-child {
    @apply truncate py-2 pl-2;
  }
</style>
