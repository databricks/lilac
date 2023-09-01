<script lang="ts">
  import {queryConcepts} from '$lib/queries/conceptQueries';

  import {computeSignalMutation, querySettings} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getSettingsContext} from '$lib/stores/settingsStore';
  import {
    conceptDisplayName,
    displayPath,
    getComputedEmbeddings,
    getDefaultSearchPath,
    getSearchEmbedding,
    getSearches,
    getSortedConcepts,
    shortFieldName
  } from '$lib/view_utils';
  import {
    childFields,
    deserializePath,
    getSignalInfo,
    isNumeric,
    pathIncludes,
    serializePath,
    type LilacSchema,
    type Op,
    type Path,
    type SignalInfoWithTypedSchema,
    type StatsResult,
    type UnaryFilter
  } from '$lilac';
  import {ComboBox, Dropdown, Tag} from 'carbon-components-svelte';
  import {Add, AssemblyCluster, Chip, Search, SearchAdvanced} from 'carbon-icons-svelte';
  import {Command, triggerCommand} from '../commands/Commands.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';

  const datasetViewStore = getDatasetViewContext();
  const datasetStore = getDatasetContext();
  const appSettings = getSettingsContext();
  $: settings = querySettings($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: namespace = $datasetViewStore.namespace;
  $: datasetName = $datasetViewStore.datasetName;

  let searchPath: Path | undefined;

  $: mediaPaths = $settings.data?.ui?.media_paths?.map(p => (Array.isArray(p) ? p : [p]));

  $: {
    if (searchPath == null && mediaPaths != null) {
      searchPath = getDefaultSearchPath($datasetStore, mediaPaths);
    }
  }

  $: searches = getSearches($datasetViewStore, searchPath);

  function getFieldSearchItems(
    searchPath: Path | undefined,
    stats: StatsResult[] | null,
    schema: LilacSchema | null,
    embeddings: SignalInfoWithTypedSchema[] | undefined
  ): SearchItem[] {
    if (schema == null || stats == null || searchPath == null) {
      return [];
    }
    const allFields = schema ? childFields(schema) : [];
    const items: SearchItem[] = [];
    for (const field of allFields) {
      if (field.dtype == null) {
        // Ignore non-pedals.
        continue;
      }
      if (field.dtype === 'embedding' || field.dtype === 'binary') {
        // Ignore special dtypes.
        continue;
      }
      if (!pathIncludes(field.path, searchPath)) {
        // Ignore any fields unrelated to the current search path.
        continue;
      }
      const signal = getSignalInfo(field);
      if (signal?.signal_name === 'concept_score') {
        // Ignore any concept scores since they are handled seperately via preview.
        continue;
      }
      const isEmbedding = embeddings?.some(e => e.name === signal?.signal_name);
      if (isEmbedding) {
        // Ignore any embeddings since they are special "index" fields.
        continue;
      }
      const shortName = shortFieldName(field.path);
      const text = displayPath(field.path.slice(searchPath.length));
      // Suggest sorting for numeric fields.
      if (isNumeric(field.dtype)) {
        items.push({
          id: {type: 'field', path: field.path, sort: 'DESC', isSignal: signal != null} as FieldId,
          text,
          description: `Sort descending by ${shortName}`
        });
        continue;
      }

      // Suggest "exists" for signal string fields such as PII.
      if (field.dtype === 'string' || field.dtype === 'string_span') {
        if (signal == null) {
          // Skip filtering source fields by EXISTS.
          continue;
        }
        items.push({
          id: {type: 'field', path: field.path, op: 'exists', isSignal: signal != null} as FieldId,
          text,
          description: `Find documents with ${shortName}`
        });
        continue;
      }
    }
    return items;
  }

  $: fieldSearchItems = getFieldSearchItems(
    searchPath,
    $datasetStore.stats,
    $datasetStore.schema,
    $embeddings.data
  );

  const signalMutation = computeSignalMutation();

  // Get the embeddings.
  const embeddings = queryEmbeddings();

  $: selectedEmbedding = getSearchEmbedding(
    $settings.data,
    $appSettings,
    $datasetStore,
    searchPath,
    ($embeddings.data || []).map(e => e.name)
  );

  // Populate existing embeddings for the selected field.
  $: existingEmbeddings = getComputedEmbeddings($datasetStore, searchPath);

  $: isEmbeddingComputed =
    existingEmbeddings != null && !!existingEmbeddings.includes(selectedEmbedding || '');

  const indexingKey = (path: Path | undefined, embedding: string | null) =>
    `${serializePath(path || '')}_${embedding}`;
  let isWaitingForIndexing: {[key: string]: boolean} = {};
  $: isIndexing =
    !isEmbeddingComputed && isWaitingForIndexing[indexingKey(searchPath, selectedEmbedding)];

  $: placeholderText = isEmbeddingComputed
    ? 'Search by keyword, field or concept.'
    : 'Search by keyword or field. Compute embedding to enable concept search.';

  const concepts = queryConcepts();
  const authInfo = queryAuthInfo();
  $: userId = $authInfo.data?.user?.id;

  $: namespaceConcepts = isEmbeddingComputed ? getSortedConcepts($concepts.data || [], userId) : [];
  interface ConceptId {
    type: 'concept';
    namespace: string;
    name: string;
  }
  interface FieldId {
    type: 'field';
    path: Path;
    isSignal: boolean;
    op?: Op;
    sort?: 'ASC' | 'DESC';
  }
  interface SearchItem {
    id:
      | ConceptId
      | FieldId
      | 'new-concept'
      | 'keyword-search'
      | 'semantic-search'
      | 'compute-embedding';
    text: string;
    description?: string;
  }
  let searchItems: SearchItem[] = [];

  let searchText = '';
  let newConceptItem: SearchItem;
  $: newConceptItem = {
    id: 'new-concept',
    text: searchText
  };
  $: keywordSearchItem = {
    id: 'keyword-search',
    text: searchText
  } as SearchItem;
  $: semanticSearchItem = {
    id: 'semantic-search',
    text: searchText
  } as SearchItem;
  $: computeEmbeddingItem = {
    id: 'compute-embedding',
    text: 'Compute embedding',
    disabled: isIndexing
  } as SearchItem;
  $: searchItems = $concepts?.data
    ? [
        ...(searchText != '' ? [keywordSearchItem] : []),
        ...(searchText != '' && selectedEmbedding && isEmbeddingComputed
          ? [semanticSearchItem]
          : []),
        ...(isEmbeddingComputed ? [newConceptItem] : [computeEmbeddingItem]),
        ...fieldSearchItems,
        ...namespaceConcepts.flatMap(namespaceConcept =>
          namespaceConcept.concepts.map(c => ({
            id: {namespace: c.namespace, name: c.name, type: 'concept'} as ConceptId,
            text: conceptDisplayName(c.namespace, c.name, $authInfo.data),
            description: c.metadata.description,
            disabled: searches.some(
              s =>
                s.type === 'concept' &&
                s.concept_namespace === c.namespace &&
                s.concept_name === c.name
            )
          }))
        )
      ]
    : [];

  function computeEmbedding() {
    if (selectedEmbedding == null) return;
    isWaitingForIndexing[indexingKey(searchPath, selectedEmbedding)] = true;
    $signalMutation.mutate([
      namespace,
      datasetName,
      {
        leaf_path: deserializePath(searchPath || []),
        signal: {
          signal_name: selectedEmbedding
        }
      }
    ]);
  }

  let comboBox: ComboBox;
  const searchConcept = (namespace: string, name: string) => {
    if (searchPath == null || selectedEmbedding == null) return;
    datasetViewStore.addSearch({
      path: searchPath,
      type: 'concept',
      concept_namespace: namespace,
      concept_name: name,
      embedding: selectedEmbedding
    });
    comboBox.clear();
  };

  const selectSearchItem = (
    e: CustomEvent<{
      selectedId: SearchItem['id'];
      selectedItem: SearchItem;
    }>
  ) => {
    if (searchPath == null) return;
    if (e.detail.selectedId === 'new-concept') {
      if (searchText === newConceptItem.id) searchText = '';
      const conceptSplit = searchText.split('/', 2);
      let conceptNamespace = '';
      let conceptName = '';
      if (conceptSplit.length === 2) {
        [conceptNamespace, conceptName] = conceptSplit;
      } else {
        [conceptName] = conceptSplit;
      }
      triggerCommand({
        command: Command.CreateConcept,
        namespace: conceptNamespace,
        conceptName,
        dataset: {namespace, name: datasetName},
        path: searchPath,
        onCreate: e => searchConcept(e.detail.namespace, e.detail.name)
      });
    } else if (e.detail.selectedId === 'keyword-search') {
      if (searchText == '') {
        return;
      }
      datasetViewStore.addSearch({
        path: searchPath,
        type: 'keyword',
        query: searchText
      });
    } else if (e.detail.selectedId == 'semantic-search') {
      if (searchText == '' || selectedEmbedding == null) {
        return;
      }
      datasetViewStore.addSearch({
        path: searchPath,
        type: 'semantic',
        query: searchText,
        embedding: selectedEmbedding
      });
    } else if (e.detail.selectedId == 'compute-embedding') {
      computeEmbedding();
    } else if (e.detail.selectedId.type === 'concept') {
      searchConcept(e.detail.selectedId.namespace, e.detail.selectedId.name);
    } else if (e.detail.selectedId.type === 'field') {
      const searchItem = e.detail.selectedId as FieldId;
      if (searchItem.sort != null) {
        datasetViewStore.setSortBy(searchItem.path);
        datasetViewStore.setSortOrder(searchItem.sort);
      } else if (searchItem.op != null) {
        datasetViewStore.addFilter({
          path: searchItem.path,
          op: searchItem.op
        } as UnaryFilter);
      } else {
        throw new Error(`Unknown search type ${e.detail.selectedId}`);
      }
    } else {
      throw new Error(`Unknown search type ${e.detail.selectedId}`);
    }
    comboBox.clear();
  };
  const selectField = (e: CustomEvent) => {
    searchPath = e.detail.selectedItem.path as Path;
  };

  let dropdownItems: {id: string; text: string; path: Path; embeddings: string[]}[] = [];
  $: dropdownItems = (mediaPaths || []).map(p => ({
    id: serializePath(p),
    text: displayPath(p),
    path: p,
    embeddings: getComputedEmbeddings($datasetStore, p)
  }));
</script>

<!-- Search boxes -->
<div class="flex h-full w-full flex-grow items-center">
  <div class="flex w-full rounded border border-gray-200">
    <div
      class="search-icon flex items-center"
      use:hoverTooltip={{text: 'Select the field to search over.'}}
    >
      <Search class="ml-2 mr-px" size={16} />
    </div>
    <div class="embedding-dropdown rounded border-r border-gray-200">
      <Dropdown
        size="xl"
        class="w-48"
        on:select={selectField}
        disabled={searchPath == null}
        selectedId={searchPath ? serializePath(searchPath) : dropdownItems[0]?.id}
        items={dropdownItems}
        let:item
      >
        {@const dropdownItem = dropdownItems.find(x => x === item)}
        <div class="flex h-full w-full items-center justify-between gap-x-1">
          {#if dropdownItem}
            <div class="w-full flex-grow truncate">
              {dropdownItem.text}
            </div>
            {#if dropdownItem.embeddings.length > 0}
              <div
                use:hoverTooltip={{
                  text: `Computed embeddings: ${dropdownItem.embeddings.join(', ')}`
                }}
              >
                <Tag><AssemblyCluster /></Tag>
              </div>
            {/if}
          {/if}
        </div>
      </Dropdown>
    </div>
    <div class="search-container w-full flex-grow">
      <ComboBox
        size="xl"
        class="w-full"
        bind:this={comboBox}
        items={searchItems}
        bind:value={searchText}
        on:select={selectSearchItem}
        shouldFilterItem={(item, value) =>
          item.text.toLowerCase().includes(value.toLowerCase()) ||
          item.id === 'new-concept' ||
          item.id === 'compute-embedding'}
        placeholder={placeholderText}
        let:item={it}
      >
        {@const item = searchItems.find(p => p.id === it.id)}
        {@const isSignal =
          item != null &&
          typeof item.id === 'object' &&
          item.id.type === 'field' &&
          item.id.isSignal}
        {@const isConcept =
          item != null && typeof item.id === 'object' && item.id.type === 'concept'}
        {#if item == null}
          <div />
        {:else if item.id === 'new-concept'}
          <div class="new-concept flex flex-row items-center justify-items-center">
            <Tag><Add /></Tag>
            <div class="ml-2">
              New concept{searchText != '' ? ':' : ''}
              {searchText}
            </div>
          </div>
        {:else if item.id === 'keyword-search'}
          <div class="new-keyword flex flex-row items-center justify-items-center">
            <Tag><SearchAdvanced /></Tag>
            <div class="ml-2">
              Keyword search:
              {searchText}
            </div>
          </div>
        {:else if item.id === 'semantic-search'}
          <div class="new-keyword flex flex-row items-center justify-items-center">
            <Tag><SearchAdvanced /></Tag>
            <div class="ml-2">
              Semantic search:
              {searchText}
            </div>
          </div>
        {:else if item.id === 'compute-embedding' && selectedEmbedding && searchPath}
          <div class="new-concept flex items-center">
            <Tag><Chip /></Tag>
            <div class="ml-2">Compute embeddings to enable concept search.</div>
          </div>
        {:else}
          <div class="flex justify-between gap-x-8" class:isSignal class:isConcept>
            <div>{item.text}</div>
            {#if item.description}
              <div class="truncate text-xs text-gray-500">{item.description}</div>
            {/if}
          </div>
        {/if}
      </ComboBox>
    </div>
  </div>
</div>

<style lang="postcss">
  .search-icon {
    background-color: rgb(250, 250, 250);
  }
  :global(.bx--form__helper-text) {
    padding: 0 0 0 1rem;
  }
  :global(.compute-embedding .bx--btn) {
    @apply h-12;
  }
  :global(.compute-embedding-indexing .bx--btn.bx--btn--disabled) {
    @apply text-transparent;
  }
  :global(.embedding-select .bx--select, .field-select .bx--select) {
    @apply flex-row;
  }
  :global(.new-concept .bx--tag, .new-keyword .bx--tag) {
    @apply w-6 min-w-0 px-0;
  }
  :global(.new-concept, .new-keyword) {
    @apply h-full;
  }
  /* Style the combobox item's parent div with a background color depending on type of search. */
  :global(.bx--list-box__menu-item:not(.bx--list-box__menu-item--highlighted):has(.isSignal)) {
    @apply bg-blue-50;
  }
  :global(.bx--list-box__menu-item:not(.bx--list-box__menu-item--highlighted):has(.isConcept)) {
    @apply bg-emerald-100;
  }
  :global(.search-container .bx--list-box__menu) {
    max-height: 26rem !important;
  }
  :global(.search-container .bx--list-box__field) {
    height: 100%;
  }
  :global(.embedding-dropdown .bx--list-box__menu-item__option) {
    padding-right: 0;
  }
</style>
