<script lang="ts">
  import {queryConcept} from '$lib/queries/conceptQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {conceptLink} from '$lib/utils';
  import {displayPath, getSearches, getSort} from '$lib/view_utils';
  import {
    deserializePath,
    formatValue,
    petals,
    serializePath,
    type Path,
    type Search,
    type SearchResultInfo,
    type SearchType,
    type WebManifest
  } from '$lilac';
  import {
    Button,
    Modal,
    Select,
    SelectItem,
    SelectItemGroup,
    SkeletonText
  } from 'carbon-components-svelte';
  import {
    ArrowUpRight,
    Close,
    Filter,
    SortAscending,
    SortDescending,
    SortRemove
  } from 'carbon-icons-svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import ConceptView from '../concepts/ConceptView.svelte';
  import AddLabel from './AddLabel.svelte';
  import FilterPill from './FilterPill.svelte';
  import GroupByDropdown from './GroupByDropdown.svelte';
  import GroupByPanel from './GroupByPanel.svelte';
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
    concept: 'Concepts',
    metadata: 'Metadata'
  };

  // Separate the searches by type.
  let searchesByType: {[searchType: string]: Search[]} = {};

  $: {
    searchesByType = {};
    for (const search of searches) {
      if (!search.type) continue;
      if (!(search.type in searchesByType)) {
        searchesByType[search.type] = [];
      }
      searchesByType[search.type].push(search);
    }
  }

  function openSearchPill(search: Search) {
    if (search.type === 'concept') {
      openedConcept = {namespace: search.concept_namespace, name: search.concept_name};
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

  $: schema = $datasetStore?.selectRowsSchema?.data?.schema;
  $: sortItems =
    schema != null
      ? [
          {path: [''], text: 'None', disabled: selectedSortBy == null && sortById !== ''},
          ...petals(schema)
            .filter(f => f.dtype != 'embedding' && f.dtype != 'string_span')
            .map(field => {
              return {
                path: field.path,
                text: displayPath(field.path.slice(1)),
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

<div class="mx-5 my-2 flex items-center justify-between">
  <div class="flex items-center gap-x-8 gap-y-2">
    <AddLabel
      addLabelsQuery={{searches, filters}}
      buttonText={'Label all'}
      helperText={'Apply label to all results within the current filter set.'}
    />
    <!-- Filters -->
    <div class="flex items-center gap-x-1">
      <div><Filter /></div>
      {#if searches.length > 0 || (filters && filters.length > 0)}
        <div class="flex flex-grow flex-row gap-x-4">
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
                {#if schema}
                  {#each filters as filter}
                    <FilterPill {schema} {filter} />
                  {/each}
                {:else}
                  <SkeletonText />
                {/if}
              </div>
            </div>
          {/if}
        </div>
      {:else}
        Filters
      {/if}
    </div>

    <GroupByDropdown />

    <!-- Sorting -->
    <div class="sort-container flex flex-row items-center gap-x-1 md:w-fit">
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
      {#if sortById === ''}
        Sort by
      {:else}
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
      {/if}
      {#if selectedSortBy != null}
        <button
          use:hoverTooltip={{text: 'Clear sort'}}
          disabled={sort == null}
          on:click={clearSorts}
        >
          <Close />
        </button>
      {/if}
    </div>
  </div>
  <!-- Number of results. -->
  <div class="flex py-2">
    {#if totalNumRows && manifest}
      {#if totalNumRows == manifest.dataset_manifest.num_items}
        {formatValue(totalNumRows)} rows
      {:else}
        {formatValue(totalNumRows)} of {formatValue(manifest.dataset_manifest.num_items)} rows
      {/if}
    {/if}
  </div>
</div>

{#if $datasetViewStore.groupBy && $datasetStore.schema}
  <GroupByPanel schema={$datasetStore.schema} groupBy={$datasetViewStore.groupBy} />
{/if}

{#if openedConcept}
  <Modal open modalHeading={''} passiveModal on:close={() => (openedConcept = null)} size="lg">
    {#if $concept?.isLoading}
      <SkeletonText />
    {:else if $concept?.isError}
      <p>{$concept.error.message}</p>
    {:else if $concept?.isSuccess}
      <div class="mb-4 ml-6">
        <Button
          size="small"
          kind="ghost"
          icon={ArrowUpRight}
          href={conceptLink($concept?.data.namespace, $concept.data.concept_name)}
          iconDescription={'Open concept page'}>Go to concept</Button
        >
      </div>

      <ConceptView concept={$concept.data} />
    {/if}
  </Modal>
{/if}

<style lang="postcss">
  .filter-group {
    min-width: 6rem;
    @apply flex flex-row items-center gap-x-2 border border-gray-200 px-2 py-1 shadow-sm;
  }
</style>
