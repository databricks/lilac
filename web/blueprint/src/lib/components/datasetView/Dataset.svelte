<script lang="ts">
  import Page from '$lib/components/Page.svelte';
  import Commands from '$lib/components/commands/Commands.svelte';
  import {hoverTooltip} from '$lib/components/common/HoverTooltip';
  import RowView from '$lib/components/datasetView/RowView.svelte';
  import SearchPanel from '$lib/components/datasetView/SearchPanel.svelte';
  import SchemaView from '$lib/components/schemaView/SchemaView.svelte';
  import {
    queryDatasetSchema,
    queryManyDatasetStats,
    querySelectRowsSchema,
    querySettings
  } from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {createDatasetStore, setDatasetContext} from '$lib/stores/datasetStore';
  import {
    createDatasetViewStore,
    getSelectRowsSchemaOptions,
    setDatasetViewContext
  } from '$lib/stores/datasetViewStore';
  import {getVisibleFields} from '$lib/view_utils';
  import {getFieldsByDtype} from '$lilac';
  import {Button, Tag} from 'carbon-components-svelte';
  import {ChevronLeft, ChevronRight, Download, Reset, Settings} from 'carbon-icons-svelte';
  import DatasetSettingsModal from './DatasetSettingsModal.svelte';
  import DownloadModal from './DownloadModal.svelte';

  export let namespace: string;
  export let datasetName: string;

  $: datasetViewStore = createDatasetViewStore(namespace, datasetName);
  $: setDatasetViewContext(datasetViewStore);

  $: schemaCollapsed = $datasetViewStore.schemaCollapsed;
  function toggleSchemaCollapsed() {
    $datasetViewStore.schemaCollapsed = !$datasetViewStore.schemaCollapsed;
  }

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);
  $: stringFields = getFieldsByDtype('string', $schema.data);
  $: stats = queryManyDatasetStats(
    $datasetViewStore.namespace,
    $datasetViewStore.datasetName,
    stringFields.map(f => f.path)
  );

  // Get the resulting schema including UDF columns
  $: selectRowsSchema = querySelectRowsSchema(
    $datasetViewStore.namespace,
    $datasetViewStore.datasetName,
    getSelectRowsSchemaOptions($datasetViewStore)
  );

  const datasetStore = createDatasetStore(namespace, datasetName);
  setDatasetContext(datasetStore);

  $: settings = querySettings($datasetViewStore.namespace, $datasetViewStore.datasetName);
  $: {
    if ($schema.data != null && $stats.data && !$stats.isFetching) {
      datasetStore.setStats($stats.data);
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
    const visibleFields = getVisibleFields(
      $datasetViewStore.selectedColumns,
      $selectRowsSchema?.data?.schema || null
    );
    datasetStore.setVisibleFields(visibleFields);
  }
  $: {
    if ($settings.data != null) {
      datasetStore.setSettings($settings.data);
    }
  }

  let settingsOpen = false;
  let downloadOpen = false;

  const authInfo = queryAuthInfo();
  $: canUpdateSettings = $authInfo.data?.access.dataset.update_settings;
</script>

<Page title={'Datasets'}>
  <div slot="header-subtext">
    <div
      use:hoverTooltip={{
        text: `${$datasetViewStore.namespace}/${$datasetViewStore.datasetName}`
      }}
    >
      <Tag type="outline">{$datasetViewStore.datasetName}</Tag>
    </div>
  </div>
  <div slot="header-center" class="flex w-full items-center">
    <SearchPanel />
  </div>
  <div slot="header-right">
    <div class="flex h-full flex-col">
      <div class="flex">
        <Button
          size="field"
          kind="ghost"
          icon={Reset}
          iconDescription="Reset View"
          on:click={datasetViewStore.reset}
        />
        <Button
          size="field"
          kind="ghost"
          icon={Download}
          iconDescription="Download data"
          on:click={() => (downloadOpen = true)}
        />
        <div
          use:hoverTooltip={{
            text: !canUpdateSettings
              ? 'User does not have access to update settings of this dataset.'
              : ''
          }}
          class:opacity-40={!canUpdateSettings}
        >
          <Button
            disabled={!canUpdateSettings}
            size="field"
            kind="ghost"
            icon={Settings}
            iconDescription="Dataset settings"
            on:click={() => (settingsOpen = true)}
          />
        </div>
      </div>
    </div>
  </div>
  <div class="flex h-full w-full">
    <div
      class={`schema-container relative h-full ${
        !schemaCollapsed ? 'w-1/3' : 'w-0'
      } border-r border-gray-200`}
    >
      <SchemaView />
      <div
        class={`absolute right-0 top-1/2 flex
                h-8 w-4 cursor-pointer items-center justify-center
                rounded border
                border-neutral-200 bg-neutral-100
                opacity-60 hover:bg-neutral-200
                hover:opacity-100
                ${schemaCollapsed ? ' translate-x-full' : ' translate-x-1/2'}`}
        use:hoverTooltip={{text: schemaCollapsed ? 'Show Schema' : 'Hide Schema'}}
        on:click={toggleSchemaCollapsed}
        on:keypress={toggleSchemaCollapsed}
      >
        {#if !schemaCollapsed}
          <ChevronLeft />
        {:else}
          <ChevronRight />
        {/if}
      </div>
    </div>
    <div class="h-full w-2/3 flex-grow"><RowView /></div>
  </div>

  {#if $schema.data}
    <DatasetSettingsModal bind:open={settingsOpen} schema={$schema.data} />
    <DownloadModal bind:open={downloadOpen} schema={$schema.data} />
  {/if}
</Page>
<Commands />

<style>
  .schema-container {
    transition: width 0.2s ease-in-out;
  }
</style>
