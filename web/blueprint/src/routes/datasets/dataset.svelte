<script lang="ts">
  import Commands from '$lib/components/commands/Commands.svelte';
  import RowView from '$lib/components/datasetView/RowView.svelte';
  import SchemaView from '$lib/components/schemaView/SchemaView.svelte';
  import {queryDatasetSchema, queryManyDatasetStats} from '$lib/queries/datasetQueries';
  import {setDatasetContext, type DatasetStore} from '$lib/stores/datasetStore';
  import {createDatasetViewStore, setDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getFieldsByDtype} from '$lilac';
  import {writable} from 'svelte/store';

  export let namespace: string;
  export let datasetName: string;

  $: datasetViewStore = createDatasetViewStore(namespace, datasetName);
  $: setDatasetViewContext(datasetViewStore);

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);
  $: stringFields = getFieldsByDtype('string', $schema.data);
  $: stats = queryManyDatasetStats(
    stringFields.map(f => {
      return [
        $datasetViewStore.namespace,
        $datasetViewStore.datasetName,
        {
          leaf_path: f.path
        }
      ];
    })
  );

  const datasetStore = writable<DatasetStore>({schema: null, stats: null});
  setDatasetContext(datasetStore);

  // Compute the stats for all string fields and write them to the dataset store. This allows us to
  // share stats about fields with all children.
  $: {
    if (
      $schema.data != null &&
      $stats.length > 0 &&
      !$stats.some(stat => stat == null || stat.isLoading)
    ) {
      const sortedStats = $stats
        .map((stats, i) => ({path: stringFields[i].path, stats}))
        .sort((a, b) => {
          if (a == null || b == null) {
            return 0;
          }
          return (b.stats.data?.avg_text_length || 0) - (a.stats.data?.avg_text_length || 0);
        });
      datasetStore.set({
        schema: $schema.data,
        stats: sortedStats
      });
    }
  }
</script>

<div class="flex h-full w-full">
  <div class=" h-full w-1/3 border-r border-gray-200">
    <SchemaView />
  </div>
  <div class="h-full w-2/3">
    <RowView />
  </div>
</div>

<Commands />
