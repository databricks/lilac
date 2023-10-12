<script lang="ts">
  import Dataset from '$lib/components/datasetView/Dataset.svelte';
  import {
    createDatasetViewStore,
    defaultDatasetViewState,
    setDatasetViewContext,
    type DatasetViewState
  } from '$lib/stores/datasetViewStore';
  import {
    deserializeState,
    getUrlHashContext,
    persistedHashStore,
    serializeState
  } from '$lib/stores/urlHashStore';

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

  $: datasetViewStore =
    namespace && datasetName ? createDatasetViewStore(namespace, datasetName) : null;
  $: {
    if (datasetViewStore != null) {
      const defaultState = defaultDatasetViewState(namespace!, datasetName!);
      persistedHashStore<DatasetViewState>(
        'datasets',
        `${namespace}/${datasetName}`,
        datasetViewStore,
        urlHashStore,
        hashState => deserializeState(hashState, defaultState),
        state => serializeState(state, defaultState)
      );
    }
  }
  $: {
    if (datasetViewStore != null) {
      setDatasetViewContext(datasetViewStore);
    }
  }
</script>

{#if datasetViewStore && namespace && datasetName}
  {#key datasetViewStore}
    <Dataset {namespace} {datasetName} />
  {/key}
{:else}
  Page not found! Please specify a dataset.
{/if}
