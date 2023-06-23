<script lang="ts">
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getSearches} from '$lib/view_utils';
  import {formatValue, type Search, type SearchType, type WebManifest} from '$lilac';
  import FilterPill from './FilterPill.svelte';
  import SearchPill from './SearchPill.svelte';

  export let totalNumRows: number | undefined;
  export let manifest: WebManifest | undefined;

  let datasetViewStore = getDatasetViewContext();

  $: searches = getSearches($datasetViewStore);

  $: filters = $datasetViewStore.queryOptions.filters;

  const searchTypeOrder: SearchType[] = ['keyword', 'semantic', 'concept'];
  const searchTypeDisplay: {[searchType in SearchType]: string} = {
    keyword: 'Keyword',
    semantic: 'Semantic',
    concept: 'Concepts'
  };

  // Separate the searches by type.
  let searchesByType: {[searchType: string]: Search[]} = {};

  $: {
    searchesByType = {};
    for (const search of searches) {
      if (!search.query.type) continue;
      if (!(search.query.type in searchesByType)) {
        searchesByType[search.query.type] = [];
      }
      searchesByType[search.query.type].push(search);
    }
  }
</script>

<div class="m-4 flex items-center justify-between">
  <div class="flex flex-row gap-x-4">
    <!-- Search groups -->
    {#each searchTypeOrder as searchType}
      {#if searchesByType[searchType]}
        <div class="filter-group rounded bg-slate-50 px-2 py-1 shadow-sm">
          <div class="mb-2 ml-2 text-xs font-light">{searchTypeDisplay[searchType]}</div>

          <div class="flex flex-row gap-x-1">
            {#each searchesByType[searchType] as search}
              <SearchPill {search} />
            {/each}
          </div>
        </div>
      {/if}
    {/each}
    <!-- Filters group -->
    {#if filters != null && filters.length > 0}
      <div class="filter-group rounded bg-slate-50 px-2 py-1 shadow-sm">
        <div class="mb-2 ml-2 text-xs font-light">Filters</div>
        <div class="flex flex-row gap-x-1">
          {#each filters as filter}
            <FilterPill {filter} />
          {/each}
        </div>
      </div>
    {/if}
  </div>
  <div>
    {#if totalNumRows && manifest}
      {formatValue(totalNumRows)} of {formatValue(manifest.dataset_manifest.num_items)} rows
    {/if}
  </div>
</div>

<style lang="postcss">
  .filter-group {
    min-width: 6rem;
    @apply border border-gray-200 px-2 py-3 shadow-sm;
  }
</style>
