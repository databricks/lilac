<script lang="ts">
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import type {KeywordQuery, Search, SearchType, SemanticQuery} from '$lilac';
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
      ? `${search.query.concept_namespace}/${search.query.concept_name}`
      : (search.query as KeywordQuery | SemanticQuery).search;
  $: tagType = search.query.type != null ? searchTypeToTagType[search.query.type] : 'outline';
</script>

<button
  class="search-pill items-center text-left"
  use:hoverTooltip={{
    component: SearchPillHoverBody,
    props: {search, tagType}
  }}
  on:click
>
  <RemovableTag
    title={'query'}
    interactive
    type={tagType}
    on:remove={() =>
      datasetViewStore.removeSearch(search, $datasetStore.selectRowsSchema?.data || null)}
    >{pillText}
  </RemovableTag>
</button>
