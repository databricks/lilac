<script lang="ts">
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getSearches} from '$lib/view_utils';
  import type {Search, SearchType} from '$lilac';
  import SearchPill from './SearchPill.svelte';

  let datasetViewStore = getDatasetViewContext();

  $: searches = getSearches($datasetViewStore);

  const searchTypeOrder: SearchType[] = ['contains', 'semantic'];
  const searchTypeDisplay: {[searchType in SearchType]: string} = {
    contains: 'Keyword',
    semantic: 'Semantic'
  };

  // Separate the searches by type.
  let searchesByType: {[searchType: string]: Search[]} = {};

  $: {
    searchesByType = {};
    for (const search of searches) {
      if (!(search.type in searchesByType)) {
        searchesByType[search.type] = [];
      }
      searchesByType[search.type].push(search);
    }
  }
</script>

<div class="mb-2 ml-4 flex flex-row">
  {#each searchTypeOrder as searchType}
    {#if searchesByType[searchType]}
      <div class="search-type mr-4 rounded bg-slate-50 px-2 py-1 shadow-sm">
        <div class="mb-2 ml-2 text-xs font-light">{searchTypeDisplay[searchType]}</div>

        {#each searchesByType[searchType] as search}
          <SearchPill {search} />
        {/each}
      </div>
    {/if}
  {/each}
</div>

<style lang="postcss">
  .search-type {
    min-width: 6rem;
  }
</style>
