<script lang="ts">
  import Dataset from '$lib/components/datasetView/Dataset.svelte';
  import {getUrlHashContext} from '$lib/stores/urlHashStore';
  import Datasets from './Datasets.svelte';

  let namespace: string | undefined = undefined;
  let datasetName: string | undefined = undefined;
  const urlHashStore = getUrlHashContext();

  $: {
    if ($urlHashStore.page === 'datasets') {
      if ($urlHashStore.identifier == '' || $urlHashStore.identifier == null) {
        namespace = undefined;
        datasetName = undefined;
      } else {
        const [newNamespace, newDataset] = $urlHashStore.identifier.split('/');
        if (namespace != newNamespace || datasetName != newDataset) {
          namespace = newNamespace;
          datasetName = newDataset;
        }
      }
    }
  }
</script>

{#if namespace != null && datasetName != null}
  <Dataset {namespace} {datasetName} />
{:else}
  <Datasets />
{/if}
