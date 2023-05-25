<script lang="ts">
  import {queryDatasetSchema, queryDatasetStats} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext, isPathVisible} from '$lib/stores/datasetViewStore';
  import {listFields, type Path} from '$lilac';
  import {TextInput} from 'carbon-components-svelte';

  let datasetViewStore = getDatasetViewContext();

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);

  let visibleStringFields: Path[] = [];
  $: {
    let allFields = $schema?.isSuccess ? listFields($schema.data) : [];
    visibleStringFields = allFields
      .filter(f => isPathVisible($datasetViewStore.visibleColumns, f.path, undefined))
      .filter(f => f.dtype == 'string')
      .map(f => f.path);
  }

  $: statsQueries = visibleStringFields.map(path =>
    queryDatasetStats($datasetViewStore.namespace, $datasetViewStore.datasetName, {
      leaf_path: path
    })
  );

  $: {
    statsQueries.forEach(query => {
      console.log($query?.isSuccess);
    });
  }

  let searchText = '';
  console.log(searchText);
  const search = () => {
    console.log(searchText);
    datasetViewStore;
  };
</script>

<div class="search-container mx-4 mb-2">
  <TextInput
    labelText="Search"
    bind:value={searchText}
    on:keydown={e => (e.key == 'Enter' ? search() : null)}
    size="sm"
  />
</div>

<style lang="postcss">
  .search-container {
    width: 30rem;
  }
</style>
