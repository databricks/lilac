<script lang="ts">
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {displayPath} from '$lib/view_utils';
  import type {KeywordSearch, Search, SearchType, SemanticSearch} from '$lilac';
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
    search.type === 'concept'
      ? search.concept_name
      : (search as KeywordSearch | SemanticSearch).query;
  $: tagType = search.type != null ? searchTypeToTagType[search.type] : 'outline';
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
    ><span class="font-mono">{displayPath(search.path)}</span> has "{pillText}"
  </RemovableTag>
</div>
