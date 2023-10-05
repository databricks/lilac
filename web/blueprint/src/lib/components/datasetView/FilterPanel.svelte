<script lang="ts">
  import {queryConcept} from '$lib/queries/conceptQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {conceptLink} from '$lib/utils';
  import {getSearches} from '$lib/view_utils';
  import {formatValue, type Search, type SearchType, type WebManifest} from '$lilac';
  import {Button, Modal, SkeletonText} from 'carbon-components-svelte';
  import {ArrowUpRight, Filter} from 'carbon-icons-svelte';
  import ConceptView from '../concepts/ConceptView.svelte';
  import AddLabel from './AddLabel.svelte';
  import FilterPill from './FilterPill.svelte';
  import GroupByPanel from './GroupByPanel.svelte';
  import GroupByPill from './GroupByPill.svelte';
  import SearchPill from './SearchPill.svelte';
  import SortPill from './SortPill.svelte';

  export let totalNumRows: number | undefined;
  export let manifest: WebManifest | undefined;

  let datasetViewStore = getDatasetViewContext();
  let datasetStore = getDatasetContext();
  const authInfo = queryAuthInfo();
  $: canLabelAll = $authInfo.data?.access.dataset.label_all || false;

  $: schema = $datasetStore?.selectRowsSchema?.data?.schema;

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
</script>

<div class="relative mx-5 my-2 flex items-center justify-between">
  <div class="flex items-center gap-x-6 gap-y-2">
    <AddLabel
      disabled={!canLabelAll}
      disabledMessage={!canLabelAll ? 'User does not have access to label all.' : ''}
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

    <GroupByPill />
    <SortPill />
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
