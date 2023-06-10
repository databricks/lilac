<script lang="ts">
  import {queryConcepts} from '$lib/queries/conceptQueries';
  import {computeSignalColumnMutation} from '$lib/queries/datasetQueries';

  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {SEARCH_TABS, getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {
    getComputedEmbeddings,
    getSearchEmbedding,
    getSearchPath,
    getSearches,
    getSort
  } from '$lib/view_utils';
  import {deserializePath, petals, serializePath, type Path, type SearchResultInfo} from '$lilac';
  import {
    Button,
    ComboBox,
    Dropdown,
    InlineLoading,
    Search,
    Select,
    SelectItem,
    Tab,
    TabContent,
    Tabs,
    Tag
  } from 'carbon-components-svelte';
  import {
    Add,
    Checkmark,
    Chip,
    Close,
    SortAscending,
    SortDescending,
    SortRemove
  } from 'carbon-icons-svelte';
  import {Command, triggerCommand} from '../commands/Commands.svelte';

  let datasetViewStore = getDatasetViewContext();
  let datasetStore = getDatasetContext();

  $: namespace = $datasetViewStore.namespace;
  $: datasetName = $datasetViewStore.datasetName;

  $: selectedTab = $datasetViewStore.searchTab;
  $: selectedTabIndex = Object.values(SEARCH_TABS).findIndex(v => v === selectedTab);

  $: searchPath = getSearchPath($datasetViewStore, $datasetStore);

  let keywordSearchText: string;
  let semanticSearchText: string;

  $: searches = getSearches($datasetViewStore, searchPath);

  const computeSignalMutation = computeSignalColumnMutation();

  // Only show the visible string fields in the dropdown.
  $: visibleStringPaths = ($datasetStore?.visibleFields || [])
    .filter(f => f.dtype === 'string')
    .map(f => serializePath(f.path));

  // Get the embeddings.
  const embeddings = queryEmbeddings();

  $: selectedEmbedding = getSearchEmbedding(
    $datasetViewStore,
    $datasetStore,
    searchPath,
    ($embeddings.data || []).map(e => e.name)
  );

  // Populate existing embeddings for the selected field.
  $: existingEmbeddings = getComputedEmbeddings($datasetStore, searchPath);

  $: isEmbeddingComputed =
    existingEmbeddings != null && !!existingEmbeddings.includes(selectedEmbedding || '');

  const indexingKey = (path: Path | null, embedding: string | null) =>
    `${serializePath(path || '')}_${embedding}`;
  let isWaitingForIndexing: {[key: string]: boolean} = {};
  $: isIndexing =
    !isEmbeddingComputed && isWaitingForIndexing[indexingKey(searchPath, selectedEmbedding)];

  $: keywordSearchEnabled = SEARCH_TABS[selectedTabIndex] === 'Keyword' && searchPath != null;

  // Don't show the search button the concepts tab since it is a dropdown.
  $: showSearchButton = isEmbeddingComputed && selectedTab != 'Concepts';

  $: searchButtonDisabled = selectedTab === 'Concepts' && isEmbeddingComputed;

  const concepts = queryConcepts();
  interface ConceptId {
    namespace: string;
    name: string;
  }
  interface ConceptSelectItem {
    id: ConceptId | 'new-concept';
    text: string;
  }
  let conceptSelectItems: ConceptSelectItem[] = [];

  let newConceptItem: ConceptSelectItem;
  $: newConceptItem = {
    id: 'new-concept',
    text: conceptSearchText
  };
  let conceptSearchText = '';
  $: conceptSelectItems = $concepts?.data
    ? [
        newConceptItem,
        ...$concepts.data.map(c => ({
          id: {namespace: c.namespace, name: c.name},
          text: `${c.namespace}/${c.name}`,
          disabled: searches.some(
            s =>
              s.query.type === 'concept' &&
              s.query.concept_namespace === c.namespace &&
              s.query.concept_name === c.name
          )
        }))
      ]
    : [];

  // Sorts.
  $: sort = getSort($datasetStore);
  let pathToSearchResult: {[path: string]: SearchResultInfo} = {};
  $: {
    for (const search of $datasetStore?.selectRowsSchema?.data?.search_results || []) {
      pathToSearchResult[serializePath(search.result_path)] = search;
    }
  }

  // Server sort response.
  $: sortById = sort?.path ? serializePath(sort.path) : null;
  // Explicit user selection of sort.
  $: selectedSortBy = $datasetViewStore.queryOptions.sort_by;

  $: sortItems =
    $datasetStore?.selectRowsSchema?.data?.data_schema != null
      ? [
          {id: null, text: 'None', disabled: selectedSortBy == null && sortById != null},
          ...petals($datasetStore.selectRowsSchema.data.schema).map(field => {
            const pathStr = serializePath(field.path);
            const search = pathToSearchResult[pathStr];
            return {
              id: pathStr,
              text: search?.alias != null ? search.alias : pathStr
            };
          })
        ]
      : [];

  const search = () => {
    if (searchPath == null) {
      return;
    }
    if (selectedTab === 'Keyword') {
      if (keywordSearchText == '') {
        return;
      }
      datasetViewStore.addSearch({
        path: [serializePath(searchPath)],
        query: {
          type: 'keyword',
          search: keywordSearchText
        }
      });
      keywordSearchText = '';
    } else if (selectedTab === 'Semantic') {
      if (selectedEmbedding == null || semanticSearchText == '') {
        return;
      }
      datasetViewStore.addSearch({
        path: [serializePath(searchPath)],
        query: {
          type: 'semantic',
          search: semanticSearchText,
          embedding: selectedEmbedding
        }
      });
      semanticSearchText = '';
    }
  };

  const selectEmbedding = (e: Event) => {
    selectedEmbedding = (e.target as HTMLInputElement).value;
    datasetViewStore.setSearchEmbedding((e.target as HTMLInputElement).value);
  };
  const computeEmbedding = () => {
    if (selectedEmbedding == null) return;
    isWaitingForIndexing[indexingKey(searchPath, selectedEmbedding)] = true;
    $computeSignalMutation.mutate([
      namespace,
      datasetName,
      {
        leaf_path: deserializePath(searchPath || []),
        signal: {
          signal_name: selectedEmbedding
        }
      }
    ]);
  };

  let conceptComboBox: ComboBox;
  const searchConcept = (namespace: string, name: string) => {
    if (searchPath == null || selectedEmbedding == null) return;
    datasetViewStore.addSearch({
      path: [serializePath(searchPath)],
      query: {
        type: 'concept',
        concept_namespace: namespace,
        concept_name: name,
        embedding: selectedEmbedding
      }
    });
    conceptComboBox.clear();
  };

  const selectConcept = (
    e: CustomEvent<{
      selectedId: ConceptId | 'new-concept';
      selectedItem: ConceptSelectItem;
    }>
  ) => {
    if (searchPath == null || selectedEmbedding == null) return;
    if (e.detail.selectedId === 'new-concept') {
      if (conceptSearchText === newConceptItem.id) conceptSearchText = '';
      const conceptSplit = conceptSearchText.split('/', 2);
      let namespace = '';
      let conceptName = '';
      if (conceptSplit.length === 2) {
        [namespace, conceptName] = conceptSplit;
      } else {
        [conceptName] = conceptSplit;
      }

      triggerCommand({
        command: Command.CreateConcept,
        namespace,
        conceptName,
        onCreate: e => searchConcept(e.detail.namespace, e.detail.name)
      });
      conceptComboBox.clear();
      return;
    }
    searchConcept(e.detail.selectedId.namespace, e.detail.selectedId.name);
  };

  const selectField = (e: Event) => {
    datasetViewStore.setSearchPath((e.target as HTMLInputElement).value);
  };
  const selectTab = (e: {detail: number}) => {
    datasetViewStore.setSearchTab(SEARCH_TABS[e.detail]);
  };
  const selectSort = (e: {detail: {selectedId: string}}) => {
    if (e.detail.selectedId == null) {
      datasetViewStore.setSortBy(null);
      return;
    }
    const alias = pathToSearchResult[e.detail.selectedId]?.alias;
    if (alias != null) {
      datasetViewStore.setSortBy([alias]);
    } else {
      datasetViewStore.setSortBy(deserializePath(e.detail.selectedId));
    }
  };
  const clearSorts = () => {
    datasetViewStore.clearSorts();
  };
  const toggleSortOrder = () => {
    // Set the sort given by the select rows schema explicitly.
    if (sort != null) {
      if (sort.alias != null) {
        datasetViewStore.setSortBy([sort?.alias]);
      } else {
        datasetViewStore.setSortBy(sort.path);
      }
    }
    datasetViewStore.setSortOrder(sort?.order === 'ASC' ? 'DESC' : 'ASC');
  };
</script>

<div class="mx-4 my-2 flex h-24 flex-row items-start">
  <div class="mr-8 mt-4">
    {#key visibleStringPaths}
      <!-- Field select -->
      <Select
        class="field-select w-32"
        selected={searchPath ? serializePath(searchPath) : ''}
        on:change={selectField}
        labelText={'Search field'}
        disabled={visibleStringPaths.length === 0}
        warn={visibleStringPaths.length === 0}
        warnText={visibleStringPaths.length === 0 ? 'Select a field' : undefined}
      >
        {#each visibleStringPaths as field}
          <SelectItem value={serializePath(field)} text={serializePath(field)} />
        {/each}
      </Select>
    {/key}
  </div>
  <!-- Search boxes -->
  <div class="search-container flex w-full flex-grow flex-row">
    <div class="w-full">
      <Tabs class="flex flex-row" selected={selectedTabIndex} on:change={selectTab}>
        <Tab>{SEARCH_TABS[0]}</Tab>
        <Tab>{SEARCH_TABS[1]}</Tab>
        <Tab>{SEARCH_TABS[2]}</Tab>
        <svelte:fragment slot="content">
          <div class="flex flex-row">
            <!-- Keyword input -->
            <TabContent class="w-full">
              <Search
                placeholder="Search by keywords"
                disabled={!keywordSearchEnabled}
                bind:value={keywordSearchText}
                on:keydown={e => (e.key == 'Enter' ? search() : null)}
              />
            </TabContent>

            <!-- Semantic input -->
            <TabContent class="w-full">
              <div class="flex flex-row items-start justify-items-start">
                <div class="flex-grow">
                  <Search
                    placeholder={isEmbeddingComputed
                      ? 'Search by natural language'
                      : 'No index found. Please run the embedding index.'}
                    disabled={!isEmbeddingComputed}
                    bind:value={semanticSearchText}
                    on:keydown={e => (e.key == 'Enter' ? search() : null)}
                  />
                </div>
              </div>
            </TabContent>

            <!-- Concept input -->
            <TabContent class="w-full">
              <div class="flex w-full flex-row items-start justify-items-start">
                <div class="flex-grow">
                  <ComboBox
                    size="xl"
                    bind:this={conceptComboBox}
                    items={conceptSelectItems}
                    bind:value={conceptSearchText}
                    disabled={!isEmbeddingComputed}
                    on:select={selectConcept}
                    shouldFilterItem={(item, value) =>
                      item.text.toLowerCase().includes(value.toLowerCase()) ||
                      item.id === 'new-concept'}
                    placeholder="Search by concept"
                    let:item
                  >
                    {#if item.id === 'new-concept'}
                      <div class="new-concept flex flex-row items-center justify-items-center">
                        <Tag><Add /></Tag>
                        <div class="ml-2">
                          New concept{conceptSearchText != '' ? ':' : ''}
                          {conceptSearchText}
                        </div>
                      </div>
                    {:else}
                      <div>{item.text}</div>
                    {/if}
                  </ComboBox>
                </div>
              </div>
            </TabContent>
            {#if selectedTab === 'Semantic' || selectedTab === 'Concepts'}
              <div class="embedding-select w-40">
                <Select
                  noLabel={true}
                  on:change={selectEmbedding}
                  selected={selectedEmbedding || ''}
                  name={selectedEmbedding || ''}
                  helperText={'Embedding'}
                >
                  {#each $embeddings.data || [] as embedding}
                    <SelectItem value={embedding.name} text={embedding.name} />
                  {/each}
                </Select>
              </div>
              <div class="ml-2">
                <Button
                  class="w-24"
                  disabled={searchButtonDisabled || isIndexing}
                  on:click={() => {
                    if (isEmbeddingComputed) {
                      search();
                    } else {
                      computeEmbedding();
                    }
                  }}
                  icon={isEmbeddingComputed
                    ? selectedTab === 'Concepts'
                      ? Checkmark
                      : undefined
                    : isIndexing
                    ? InlineLoading
                    : Chip}
                >
                  {showSearchButton ? 'Search' : 'Index'}
                </Button>
              </div>
            {/if}
          </div>
        </svelte:fragment>
      </Tabs>
    </div>
  </div>

  <div class="ml-2 mt-10 flex flex-row rounded">
    <div class="w-12">
      {#if selectedSortBy != null}
        <Button
          kind="ghost"
          icon={Close}
          expressive={true}
          on:click={clearSorts}
          disabled={sort == null}
          iconDescription={sort?.order === 'ASC'
            ? 'Sorted ascending. Toggle to switch to descending.'
            : 'Sorted descending. Toggle to switch to ascending.'}
        />
      {/if}
    </div>
    <Dropdown
      size="xl"
      class="w-32"
      selectedId={sortById}
      on:select={selectSort}
      items={sortItems}
      helperText={'Sort by'}
    />
    <div>
      <Button
        kind="ghost"
        expressive={true}
        icon={sort?.order == null
          ? SortRemove
          : sort?.order === 'ASC'
          ? SortAscending
          : SortDescending}
        on:click={toggleSortOrder}
        disabled={sort == null}
        iconDescription={sort?.order === 'ASC'
          ? 'Sorted ascending. Toggle to switch to descending.'
          : 'Sorted descending. Toggle to switch to ascending.'}
      />
    </div>
  </div>
</div>

<style lang="postcss">
  :global(.bx--tabs__nav) {
    @apply flex w-full flex-row;
  }
  :global(.bx--tabs__nav-item) {
    @apply w-28;
  }
  :global(.bx--tabs__nav-item .bx--tabs__nav-link) {
    @apply w-28;
  }

  :global(.bx--form__helper-text) {
    padding: 0 0 0 1rem;
  }
  :global(.bx--btn--sm) {
    height: 2.5rem;
    @apply w-24;
    @apply px-3;
  }
  :global(.embedding-select .bx--select-input) {
    @apply h-12;
  }
  :global(.field-select .bx--select-input) {
    @apply h-12;
  }
  :global(.new-concept .bx--tag) {
    @apply w-6 min-w-0 px-0;
  }
</style>
