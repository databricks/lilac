<script lang="ts">
  import Dataset from '$lib/components/datasetView/Dataset.svelte';
  import {
    queryDatasetSchema,
    queryManyDatasetStats,
    querySelectRowsSchema,
    querySettings
  } from '$lib/queries/datasetQueries';
  import {createDatasetStore, setDatasetContext} from '$lib/stores/datasetStore';
  import {
    createDatasetViewStore,
    defaultDatasetViewState,
    getSelectRowsSchemaOptions,
    setDatasetViewContext,
    type DatasetViewState
  } from '$lib/stores/datasetViewStore';
  import {
    deserializeState,
    getUrlHashContext,
    persistedHashStore,
    serializeState
  } from '$lib/stores/urlHashStore';
  import {getFieldsByDtype} from '$lilac';

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

  $: datasetStore = namespace && datasetName ? createDatasetStore(namespace, datasetName) : null;
  $: {
    if (datasetStore != null) {
      setDatasetContext(datasetStore);
    }
  }

  // Settings.
  $: settings = namespace && datasetName ? querySettings(namespace, datasetName) : null;
  $: {
    if (datasetStore && $settings?.data) {
      datasetStore.setSettings($settings.data);
    }
  }

  // Schema.
  $: schema = namespace && datasetName ? queryDatasetSchema(namespace, datasetName) : null;
  $: {
    if (datasetStore && $schema?.data) {
      datasetStore.setSchema($schema.data);
    }
  }

  $: stringFields = $schema?.data ? getFieldsByDtype('string', $schema.data) : null;
  $: stats =
    namespace && datasetName && stringFields
      ? queryManyDatasetStats(
          namespace,
          datasetName,
          stringFields.map(f => f.path)
        )
      : null;
  $: {
    if (datasetStore && $stats?.data && !$stats.isFetching) {
      datasetStore.setStats($stats.data);
    }
  }

  // Get the resulting schema including UDF columns.
  $: selectRowsSchema =
    namespace && datasetName && $datasetViewStore
      ? querySelectRowsSchema(namespace, datasetName, getSelectRowsSchemaOptions($datasetViewStore))
      : null;
  $: {
    if (datasetStore && $selectRowsSchema?.data) {
      datasetStore.setSelectRowsSchema($selectRowsSchema);
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
