<script lang="ts">
  import {queriesDatasetStats, queryDatasetSchema} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext, isPathVisible} from '$lib/stores/datasetViewStore';
  import {listFields, serializePath, type Path} from '$lilac';
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

  $: statsQueries = queriesDatasetStats(
    visibleStringFields.map(path => {
      return [
        $datasetViewStore.namespace,
        $datasetViewStore.datasetName,
        {
          leaf_path: path
        }
      ];
    })
  );

  let longestStringPath: string = 'none';
  $: {
    if ($statsQueries && $statsQueries.length > 0 && $statsQueries.every(q => q.isSuccess)) {
      console.log($statsQueries);
      const stats = $statsQueries.map(q => q.data);
      const pathLengths = stats
        .map((s, i) => {
          return {
            path: visibleStringFields[i],
            avg_text_length: s?.avg_text_length || 0
          };
        })
        .sort((a, b) => {
          return b.avg_text_length - a.avg_text_length;
        });

      longestStringPath = serializePath(pathLengths[0].path);
      console.log('longest path', longestStringPath);
    }
  }

  let searchText = '';
  console.log(searchText);
  const search = () => {
    console.log(searchText);
    datasetViewStore;
  };
</script>

<div class="search-container mx-4 mb-2 flex flex-row items-center justify-items-center">
  <TextInput
    labelText={`Search "${longestStringPath}"`}
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
