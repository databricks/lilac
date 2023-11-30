<script lang="ts">
  import {querySelectRowsSchema} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext, getSelectRowsSchemaOptions} from '$lib/stores/datasetViewStore';
  import {getDisplayPath} from '$lib/view_utils';
  import type {KeywordSearch, MetadataSearch, Search, SearchType, SemanticSearch} from '$lilac';
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
    concept: 'green',
    metadata: 'magenta'
  };

  const datasetViewStore = getDatasetViewContext();
  $: selectRowsSchema = querySelectRowsSchema(
    $datasetViewStore.namespace,
    $datasetViewStore.datasetName,
    getSelectRowsSchemaOptions($datasetViewStore)
  );

  function getPillText(search: Search) {
    if (search.type === 'concept') {
      return search.concept_name;
    } else if (search.type === 'keyword' || search.type === 'semantic') {
      return (search as KeywordSearch | SemanticSearch).query;
    } else if (search.type === 'metadata') {
      return (search as MetadataSearch).value;
    }
  }

  $: pillText = getPillText(search);
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
    on:remove={() => datasetViewStore.removeSearch(search, $selectRowsSchema?.data || null)}
    ><span class="font-mono">{getDisplayPath(search.path)}</span> has "{pillText}"
  </RemovableTag>
</div>
