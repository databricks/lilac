<script lang="ts">
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {
    serializePath,
    type KeywordQuery,
    type Search,
    type SearchType,
    type SemanticQuery
  } from '$lilac';
  import {Tag} from 'carbon-components-svelte';
  import HoverTooltip from '../common/HoverTooltip.svelte';
  import RemovableTag from '../common/RemovableTag.svelte';
  import EmbeddingBadge from './EmbeddingBadge.svelte';

  export let search: Search;

  const searchTypeToTagType: {
    [searchType in SearchType]: Tag['type'];
  } = {
    keyword: 'outline',
    semantic: 'teal',
    concept: 'green'
  };

  const datasetViewStore = getDatasetViewContext();
  const datasetStore = getDatasetContext();

  $: pillText =
    search.query.type === 'concept'
      ? `${search.query.concept_namespace}/${search.query.concept_name}`
      : (search.query as KeywordQuery | SemanticQuery).search;
  $: tagType = search.query.type != null ? searchTypeToTagType[search.query.type] : 'outline';
  $: searchText =
    search.query.type === 'concept' ? '' : (search.query as KeywordQuery | SemanticQuery).search;
</script>

<div class="search-pill mx-1 items-center">
  <RemovableTag
    title={'query'}
    interactive
    type={tagType}
    on:remove={() => datasetViewStore.removeSearch(search, $datasetStore?.selectRowsSchema || null)}
  >
    <HoverTooltip size="small" triggerText={pillText} hideIcon={true}>
      <div class=" flex items-center justify-items-center">
        <div class="whitespace-nowrap">
          <Tag type={tagType}>
            {serializePath(search.path)}: {search.query.type}
          </Tag>
        </div>
        {#if search.query.type === 'semantic'}
          <div class="ml-2">
            <EmbeddingBadge embedding={search.query.embedding} />
          </div>
        {/if}
      </div>
      {#if searchText}
        <div class="mt-2">{searchText}</div>
      {/if}
    </HoverTooltip>
  </RemovableTag>
</div>

<style lang="postcss">
  :global(.search-pill .bx--tooltip__label) {
    @apply mr-1 inline-block h-full truncate;
    max-width: 5rem;
  }
  :global(.search-pill .bx--tooltip__content) {
    @apply flex flex-col items-center;
  }
</style>
