<script lang="ts">
  import {useGetSchemaQuery} from '$lib/store/apiDataset';
  import {getDatasetViewContext, getSelectRowsOptions} from '$lib/store/datasetViewStore';

  const datasetViewStore = getDatasetViewContext();
  $: schema = useGetSchemaQuery($datasetViewStore.namespace, $datasetViewStore.datasetName);
  $: options = $schema.data ? getSelectRowsOptions($datasetViewStore, $schema.data) : undefined;
  $: formattedOptions = options ? JSON.stringify(options, null, 2) : '';
</script>

<pre class="whitespace-pre bg-gray-50 p-4 font-mono">
{formattedOptions}
</pre>
