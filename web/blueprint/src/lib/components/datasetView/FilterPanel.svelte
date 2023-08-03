<script lang="ts">
  import {queryConcept} from '$lib/queries/conceptQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getSearches, getSort} from '$lib/view_utils';
  import {
    deserializePath,
    formatValue,
    petals,
    serializePath,
    type ConceptQuery,
    type Path,
    type Search,
    type SearchResultInfo,
    type SearchType,
    type WebManifest
  } from '$lilac';
  import {Modal, Select, SelectItem, SelectItemGroup, SkeletonText} from 'carbon-components-svelte';
  import {Close, SortAscending, SortDescending, SortRemove} from 'carbon-icons-svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import ConceptView from '../concepts/ConceptView.svelte';
  import FilterPill from './FilterPill.svelte';
  import SearchPill from './SearchPill.svelte';

  export let totalNumRows: number | undefined;
  export let manifest: WebManifest | undefined;

  let datasetViewStore = getDatasetViewContext();
  let datasetStore = getDatasetContext();

  let openedConcept: {namespace: string; name: string} | null = null;
  $: concept = openedConcept
    ? queryConcept(openedConcept.namespace, openedConcept.name)
    : undefined;

  $: searches = getSearches($datasetViewStore);

  $: filters = $datasetViewStore.query.filters;

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

  function openSearchPill(search: Search) {
    if (search.query.type === 'concept') {
      const conceptQuery = search.query as ConceptQuery;
      openedConcept = {namespace: conceptQuery.concept_namespace, name: conceptQuery.concept_name};
    }
  }

  // Sorts.
  $: sort = getSort($datasetStore);
  let pathToSearchResult: {[path: string]: SearchResultInfo} = {};
  $: {
    for (const search of $datasetStore.selectRowsSchema?.data?.search_results || []) {
      pathToSearchResult[serializePath(search.result_path)] = search;
    }
  }

  // Server sort response.
  $: sortById = sort?.path ? serializePath(sort.path) : '';
  // Explicit user selection of sort.
  $: selectedSortBy = $datasetViewStore.query.sort_by;

  $: sortItems =
    $datasetStore.selectRowsSchema?.data?.schema != null
      ? [
          {path: [''], text: 'None', disabled: selectedSortBy == null && sortById !== ''},
          ...petals($datasetStore.selectRowsSchema.data.schema)
            .filter(f => f.dtype != 'embedding' && f.dtype != 'string_span')
            .map(field => {
              return {
                path: field.path,
                text: serializePath(field.path.slice(1)),
                disabled: false
              };
            })
        ]
      : [];
  $: sortGroups = sortItems.reduce((groups, item) => {
    const group = item.path[0];
    (groups[group] = groups[group] || []).push(item);
    return groups;
  }, {} as {[key: string]: {path?: Path; text: string; disabled: boolean}[]});

  const selectSort = (ev: CustomEvent<string | number>) => {
    const selected = ev.detail as string;
    if (selected === sortById) {
      return;
    }
    datasetViewStore.setSortBy(selected === '' ? null : deserializePath(selected));
  };
  const toggleSortOrder = () => {
    // Set the sort given by the select rows schema explicitly.
    if (sort != null) {
      datasetViewStore.setSortBy(sort.path);
    }
    datasetViewStore.setSortOrder(sort?.order === 'ASC' ? 'DESC' : 'ASC');
  };
  const clearSorts = () => {
    datasetViewStore.clearSorts();
  };
</script>

<div class="mx-5 my-2 flex flex-col gap-y-2">
  {#if searchTypeOrder.length > 0}
    <div class="flex w-full flex-row gap-x-4">
      <!-- Search groups -->
      {#each searchTypeOrder as searchType}
        {#if searchesByType[searchType]}
          <div class="filter-group rounded bg-slate-50 px-2 py-1 shadow-sm">
            <div class="text-xs font-light">{searchTypeDisplay[searchType]}</div>
            <div class="flex flex-row gap-x-1">
              {#each searchesByType[searchType] as search}
                <SearchPill {search} on:click={() => openSearchPill(search)} />
              {/each}
            </div>
          </div>
        {/if}
      {/each}
      <!-- Filters group -->
      {#if filters != null && filters.length > 0}
        <div class="filter-group rounded bg-slate-50 px-2 py-1 shadow-sm">
          <div class="text-xs font-light">Filters</div>
          <div class="flex flex-row gap-x-1">
            {#each filters as filter}
              <FilterPill {filter} />
            {/each}
          </div>
        </div>
      {/if}
    </div>
  {/if}
  <!-- Number of rows and sort. -->
  <div class="flex w-full flex-row items-center justify-between">
    <div class="py-1">
      {#if totalNumRows && manifest}
        {formatValue(totalNumRows)} of {formatValue(manifest.dataset_manifest.num_items)} rows
      {/if}
    </div>
    <div class="sort-container flex flex-row items-center gap-x-1">
      <div class="mr-1">Sort by</div>
      <Select noLabel size="sm" class="w-60" selected={sortById} on:update={selectSort}>
        {#each Object.entries(sortGroups) as [groupName, items]}
          <SelectItemGroup label={groupName}>
            {#each items as item}
              <SelectItem
                value={item.path != null ? serializePath(item.path) : undefined}
                text={item.text}
                disabled={item.disabled}
              />
            {/each}
          </SelectItemGroup>
        {/each}
      </Select>
      {#if selectedSortBy != null}
        <button
          use:hoverTooltip={{text: 'Clear sort'}}
          disabled={sort == null}
          on:click={clearSorts}
        >
          <Close />
        </button>
      {/if}
      <button
        use:hoverTooltip={{
          text:
            sort?.order === 'ASC'
              ? 'Sorted ascending. Toggle to switch to descending.'
              : 'Sorted descending. Toggle to switch to ascending.'
        }}
        disabled={sort == null}
        on:click={toggleSortOrder}
      >
        {#if sort?.order == null}
          <SortRemove />
        {:else if sort?.order === 'ASC'}
          <SortAscending />
        {:else if sort?.order === 'DESC'}
          <SortDescending />
        {/if}
      </button>
    </div>
  </div>
</div>

{#if openedConcept}
  <Modal open modalHeading="Concept" passiveModal on:close={() => (openedConcept = null)} size="lg">
    {#if $concept?.isLoading}
      <SkeletonText />
    {:else if $concept?.isError}
      <p>{$concept.error.message}</p>
    {:else if $concept?.isSuccess}
      <ConceptView concept={$concept.data} />
    {/if}
  </Modal>
{/if}

<style lang="postcss">
  .filter-group {
    min-width: 6rem;
    @apply flex flex-row items-center gap-x-2 border border-gray-200 px-2 py-2 shadow-sm;
  }
</style>
