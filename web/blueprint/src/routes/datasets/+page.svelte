<script lang="ts">
  import Dataset from '$lib/components/datasetView/Dataset.svelte';
  import {getAppStoreContext} from '$lib/stores/urlHashStore';
  import Datasets from './Datasets.svelte';

  let namespace: string | undefined = undefined;
  let datasetName: string | undefined = undefined;
  const appStore = getAppStoreContext();

  $: $appStore.onUrlChange('datasets', null, {}, (identifier, hashState) => {
    console.log('onUrlChange:datasetglobal', identifier);
    if (identifier == '') {
      namespace = undefined;
      datasetName = undefined;
    } else {
      const [newNamespace, newDataset] = identifier.split('/');
      if (namespace != newNamespace || datasetName != newDataset) {
        namespace = newNamespace;
        datasetName = newDataset;
        // initialState = stateFromHash(hashState, defaultDatasetViewState(namespace, datasetName));
      }
    }
  });
</script>

{#if namespace != null && datasetName != null}
  <Dataset {namespace} {datasetName} />
{:else}
  <Datasets />
{/if}
