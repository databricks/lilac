<script lang="ts">
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {serializePath, type Search, type SearchType} from '$lilac';
  import {Tag} from 'carbon-components-svelte';
  import HoverTooltip from '../common/HoverTooltip.svelte';
  import RemovableTag from '../common/RemovableTag.svelte';
  import EmbeddingBadge from './EmbeddingBadge.svelte';

  export let search: Search;

  const searchTypeToTagType: {[searchType in SearchType]: Tag['type']} = {
    contains: 'outline',
    semantic: 'teal'
  };

  const datasetViewStore = getDatasetViewContext();
</script>

<div class="search-pill mx-1 items-center">
  <RemovableTag
    title={'query'}
    interactive
    type={searchTypeToTagType[search.type]}
    on:remove={() => datasetViewStore.clearSearch(search)}
  >
    <HoverTooltip size="small" triggerText={search.query} hideIcon={true}>
      <div class="mb-3 flex items-center justify-items-center">
        <div class="whitespace-nowrap">
          <Tag type={searchTypeToTagType[search.type]}>
            {serializePath(search.path)}: {search.type}
          </Tag>
        </div>
        {#if search.type === 'semantic'}
          <div class="ml-2">
            <EmbeddingBadge embedding={search.embedding} />
          </div>
        {/if}
      </div>
      {search.query}
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
