<script lang="ts">
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {isColumn, type LilacSchemaField, type SemanticSearchSignal} from '$lilac';
  import {TextInput} from 'carbon-components-svelte';

  export let field: LilacSchemaField;
  export let splitter: string | undefined;
  export let embedding: string;

  const SEMANTIC_SEARCH_ALIAS = 'semantic_search_alias';

  const datasetViewStore = getDatasetViewContext();
  let searchTerm = '';

  function search() {
    // Remove existing concept_score column
    $datasetViewStore.queryOptions.columns = $datasetViewStore.queryOptions.columns?.filter(
      c => !isColumn(c) || c.alias !== SEMANTIC_SEARCH_ALIAS
    );

    if (!searchTerm) {
      $datasetViewStore.queryOptions.sort_by = [];

      if (splitter) datasetViewStore.removeVisibleColumn([...field.path, splitter, '*']);
      datasetViewStore.removeVisibleColumn([SEMANTIC_SEARCH_ALIAS]);
      return;
    }

    // Add the udf column
    datasetViewStore.addUdfColumn({
      signal_udf: {
        signal_name: 'semantic_search',
        embedding: embedding as SemanticSearchSignal['embedding'],
        split: splitter as SemanticSearchSignal['split'],
        query: searchTerm
      },
      path: field.path,
      alias: SEMANTIC_SEARCH_ALIAS
    });

    $datasetViewStore.queryOptions.sort_order = 'DESC';
    $datasetViewStore.queryOptions.sort_by = [SEMANTIC_SEARCH_ALIAS];

    // Ensure the SEMANTIC_SEARCH_ALIAS column is visible
    if (splitter) datasetViewStore.addVisibleColumn([...field.path, splitter, '*']);
    datasetViewStore.addVisibleColumn([SEMANTIC_SEARCH_ALIAS]);
  }
</script>

<TextInput
  labelText="Semantic Search"
  bind:value={searchTerm}
  on:keydown={ev => ev.key === 'Enter' && search()}
/>
