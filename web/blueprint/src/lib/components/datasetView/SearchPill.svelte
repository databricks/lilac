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
  import type {Tag} from 'carbon-components-svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import RemovableTag from '../common/RemovableTag.svelte';
  import SearchPillHoverBody from './SearchPillHoverBody.svelte';

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
      ? search.query.concept_name
      : (search.query as KeywordQuery | SemanticQuery).search;
  $: tagType = search.query.type != null ? searchTypeToTagType[search.query.type] : 'outline';
</script>

<div
  class="search-pill items-center text-left"
  use:hoverTooltip={{
    component: SearchPillHoverBody,
    props: {search, tagType}
  }}
>
  <RemovableTag
    title={'query'}
    interactive
    type={tagType}
    on:click
    on:remove={() =>
      datasetViewStore.removeSearch(search, $datasetStore.selectRowsSchema?.data || null)}
    ><span class="font-mono">{serializePath(search.path)}</span> has "{pillText}"
  </RemovableTag>
</div>
