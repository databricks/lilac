<script lang="ts">
  import Dataset from '$lib/components/datasetView/Dataset.svelte';
  import {getAppStoreContext} from '$lib/stores/appStore';
  import Datasets from './Datasets.svelte';

  let namespace: string | undefined = undefined;
  let datasetName: string | undefined = undefined;
  const appStore = getAppStoreContext();

  $: {
    if ($appStore.page === 'datasets') {
      if ($appStore.identifier == '' || $appStore.identifier == null) {
        namespace = undefined;
        datasetName = undefined;
      } else {
        const [newNamespace, newDataset] = $appStore.identifier.split('/');
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
