<script lang="ts">
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getSearches} from '$lib/view_utils';
  import type {Search, SearchType} from '$lilac';
  import SearchPill from './SearchPill.svelte';

  let datasetViewStore = getDatasetViewContext();

  $: searches = getSearches($datasetViewStore);

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

<div class="mb-2 ml-4 flex flex-row">
  {#each searchTypeOrder as searchType}
    {#if searchesByType[searchType]}
      <div class="search-type mr-4 rounded bg-slate-50 px-2 py-1 shadow-sm">
        <div class="mb-2 ml-2 text-xs font-light">{searchTypeDisplay[searchType]}</div>

        <div class="flex flex-row">
          {#each searchesByType[searchType] as search}
            <SearchPill {search} />
          {/each}
        </div>
      </div>
    {/if}
  {/each}
</div>

<style lang="postcss">
  .search-type {
    min-width: 6rem;
  }
</style>
