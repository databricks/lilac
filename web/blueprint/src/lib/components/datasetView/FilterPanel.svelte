<script lang="ts">
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getSearches} from '$lib/view_utils';
  import type {Search, SearchType} from '$lilac';
  import FilterPill from './FilterPill.svelte';
  import SearchPill from './SearchPill.svelte';

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

<div class="flex flex-row border-b border-gray-300 pb-2 pl-4">
  <!-- Search groups -->
  {#each searchTypeOrder as searchType}
    {#if searchesByType[searchType]}
      <div class="filter-group mr-4 rounded bg-slate-50 px-2 py-1 shadow-sm">
        <div class="mb-2 ml-2 text-xs font-light">{searchTypeDisplay[searchType]}</div>

        <div class="flex flex-row">
          {#each searchesByType[searchType] as search}
            <SearchPill {search} />
          {/each}
        </div>
      </div>
    {/if}
  {/each}
  <!-- Filters group -->
  {#if filters != null && filters.length > 0}
    <div class="filter-group mr-4 rounded bg-slate-50 px-2 py-1 shadow-sm">
      <div class="mb-2 ml-2 text-xs font-light">Filters</div>
      <div class="flex flex-row">
        {#each filters as filter}
          <div class="mx-1">
            <FilterPill {filter} />
          </div>
        {/each}
      </div>
    </div>
  {/if}
</div>

<style lang="postcss">
  .filter-group {
    min-width: 6rem;
    @apply border border-gray-200 px-2 py-3 shadow-sm;
  }
</style>
