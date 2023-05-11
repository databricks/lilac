<script lang="ts">
  import {useGetSchemaQuery} from '$lib/store/apiDataset';
  import {getDatasetViewContext, getSelectRowsOptions} from '$lib/store/datasetViewStore';
  import yaml from 'js-yaml';

  const datasetViewStore = getDatasetViewContext();
  $: schema = useGetSchemaQuery($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: options = $schema.data ? getSelectRowsOptions($datasetViewStore, $schema.data) : undefined;
  $: optionsYaml = yaml.dump(options);
</script>

<div class="whitespace-pre bg-gray-50 p-4 font-mono">
  {optionsYaml}
</div>
