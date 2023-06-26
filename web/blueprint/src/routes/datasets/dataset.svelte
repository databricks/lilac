<script lang="ts">
  import Commands from '$lib/components/commands/Commands.svelte';
  import RowView from '$lib/components/datasetView/RowView.svelte';
  import SchemaView from '$lib/components/schemaView/SchemaView.svelte';
  import {
    queryDatasetSchema,
    queryManyDatasetStats,
    querySelectRowsSchema
  } from '$lib/queries/datasetQueries';
  import {createDatasetStore, setDatasetContext, type StatsInfo} from '$lib/stores/datasetStore';
  import {
    createDatasetViewStore,
    getSelectRowsSchemaOptions,
    setDatasetViewContext
  } from '$lib/stores/datasetViewStore';
  import {getVisibleFields} from '$lib/view_utils';
  import {getFieldsByDtype} from '$lilac';

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

  // Get the resulting schema including UDF columns
  $: selectRowsSchema = querySelectRowsSchema(
    $datasetViewStore.namespace,
    $datasetViewStore.datasetName,
    getSelectRowsSchemaOptions($datasetViewStore)
  );

  const datasetStore = createDatasetStore();
  setDatasetContext(datasetStore);

  // Compute the stats for all string fields and write them to the dataset store. This allows us to
  // share stats about fields with all children.
  let sortedStats: StatsInfo[] | null = null;
  $: {
    if (
      $schema.data != null &&
      $stats.length > 0 &&
      !$stats.some(stat => stat == null || stat.isLoading)
    ) {
      sortedStats = $stats
        .map((stats, i) => ({path: stringFields[i].path, stats}))
        .sort((a, b) => {
          if (a == null || b == null) {
            return 0;
          }
          return (b.stats.data?.avg_text_length || 0) - (a.stats.data?.avg_text_length || 0);
        });
    }
  }

  $: {
    if ($schema.data != null) {
      datasetStore.setSchema($schema.data);
    }
  }
  $: {
    if ($selectRowsSchema != null) {
      datasetStore.setSelectRowsSchema($selectRowsSchema);
    }
  }
  $: {
    if (sortedStats != null) {
      datasetStore.setStats(sortedStats);
    }
  }
  $: {
    const visibleFields = getVisibleFields(
      $datasetViewStore.selectedColumns,
      $selectRowsSchema?.data?.schema || null
    );
    datasetStore.setVisibleFields(visibleFields);
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
