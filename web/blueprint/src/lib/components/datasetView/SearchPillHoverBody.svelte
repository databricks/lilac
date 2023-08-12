<script lang="ts">
  import {serializePath, type KeywordSearch, type Search, type SemanticSearch} from '$lilac';
  import {Tag} from 'carbon-components-svelte';
  import EmbeddingBadge from './EmbeddingBadge.svelte';

  export let search: Search;
  export let tagType: Tag['type'] = 'outline';

  $: searchText = search.type === 'concept' ? '' : (search as KeywordSearch | SemanticSearch).query;
</script>

{#if search.type === 'concept'}
  <div class="mb-2 w-full text-center text-xs">
    {search.concept_namespace} / {search.concept_name}
  </div>
{/if}
<div class="flex items-center justify-items-center">
  <div class="whitespace-nowrap">
    <Tag type={tagType}>
      {serializePath(search.path)}: {search.type}
    </Tag>
  </div>
  {#if search.type === 'semantic' || search.type === 'concept'}
    <div class="ml-2">
      <EmbeddingBadge embedding={search.embedding} />
    </div>
  {/if}
</div>
{#if searchText}
  <div class="mt-2 whitespace-pre-wrap text-left">{searchText}</div>
{/if}

<style lang="postcss">
  :global(.search-pill .bx--tooltip__label) {
    @apply mr-1 inline-block h-full truncate;
    max-width: 5rem;
  }
  :global(.search-pill .bx--tooltip__content) {
    @apply flex flex-col items-center;
  }
</style>
