<script lang="ts">
  import {page} from '$app/stores';
  import Commands from '$lib/components/commands/Commands.svelte';
  import RowView from '$lib/components/datasetView/RowView.svelte';
  import SchemaView from '$lib/components/schemaView/SchemaView.svelte';
  import {createDatasetViewStore, setDatasetViewContext} from '$lib/stores/datasetViewStore';

  $: namespace = $page.params.namespace;
  $: datasetName = $page.params.datasetName;

  $: setDatasetViewContext(createDatasetViewStore(namespace, datasetName));
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
