<script lang="ts">
  import {queryDatasetSchema} from '$lib/queries/datasetQueries';

  import {getDatasetViewContext, getSelectRowsOptions} from '$lib/stores/datasetViewStore';

  const datasetViewStore = getDatasetViewContext();
  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);
  $: options = $schema.data ? getSelectRowsOptions($datasetViewStore, $schema.data) : undefined;
  $: formattedOptions = options ? JSON.stringify(options, null, 2) : '';
</script>

<pre class="whitespace-pre bg-gray-50 p-4 font-mono">
{formattedOptions}
</pre>
