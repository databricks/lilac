<script lang="ts">
  import {serializePath, type KeywordQuery, type Search, type SemanticQuery} from '$lilac';
  import {Tag} from 'carbon-components-svelte';
  import EmbeddingBadge from './EmbeddingBadge.svelte';

  export let search: Search;
  export let tagType: Tag['type'] = 'outline';

  $: searchText =
    search.query.type === 'concept' ? '' : (search.query as KeywordQuery | SemanticQuery).search;
</script>

<div class="flex items-center justify-items-center">
  <div class="whitespace-nowrap">
    <Tag type={tagType}>
      {serializePath(search.path)}: {search.query.type}
    </Tag>
  </div>
  {#if search.query.type === 'semantic' || search.query.type === 'concept'}
    <div class="ml-2">
      <EmbeddingBadge embedding={search.query.embedding} />
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
