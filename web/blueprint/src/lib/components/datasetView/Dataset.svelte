<script lang="ts">
  import {goto} from '$app/navigation';
  import Page from '$lib/components/Page.svelte';
  import Commands from '$lib/components/commands/Commands.svelte';
  import {hoverTooltip} from '$lib/components/common/HoverTooltip';
  import RowView from '$lib/components/datasetView/RowView.svelte';
  import SearchPanel from '$lib/components/datasetView/SearchPanel.svelte';
  import SchemaView from '$lib/components/schemaView/SchemaView.svelte';
  import {queryDatasetSchema} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {datasetLink} from '$lib/utils';
  import {Button, Tag} from 'carbon-components-svelte';
  import {ChevronLeft, ChevronRight, Download, Settings, Share} from 'carbon-icons-svelte';
  import {fade} from 'svelte/transition';
  import DatasetSettingsModal from './DatasetSettingsModal.svelte';
  import DownloadModal from './DownloadModal.svelte';

  export let namespace: string;
  export let datasetName: string;

  const datasetViewStore = getDatasetViewContext();

  $: schemaCollapsed = $datasetViewStore.schemaCollapsed;
  function toggleSchemaCollapsed() {
    $datasetViewStore.schemaCollapsed = !$datasetViewStore.schemaCollapsed;
  }

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);

  let settingsOpen = false;
  let downloadOpen = false;

  const authInfo = queryAuthInfo();
  $: canUpdateSettings = $authInfo.data?.access.dataset.update_settings;

  let showCopyToast = false;

  $: link = datasetLink(namespace, datasetName);
</script>

<Page>
  <div slot="header-subtext">
    <Tag type="outline">
      <a class="font-semibold text-black" href={link} on:click={() => goto(link)}
        >{$datasetViewStore.namespace}/{$datasetViewStore.datasetName}
      </a>
    </Tag>
  </div>
  <div slot="header-center" class="flex w-full items-center">
    <SearchPanel />
  </div>
  <div slot="header-right">
    <div class="flex h-full flex-col">
      <div class="flex">
        <div class="relative">
          {#if showCopyToast}
            <div
              out:fade
              class="absolute right-12 z-50 mt-2 rounded border border-neutral-300 bg-neutral-50 px-4 py-1 text-xs"
            >
              Copied!
            </div>
          {/if}
          <Button
            size="field"
            kind="ghost"
            icon={Share}
            iconDescription="Copy the URL"
            on:click={() =>
              navigator.clipboard.writeText(location.href).then(
                () => {
                  showCopyToast = true;
                  setTimeout(() => (showCopyToast = false), 2000);
                },
                () => {
                  throw Error('Error copying link to clipboard.');
                }
              )}
          />
        </div>

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
    <DatasetSettingsModal
      bind:open={settingsOpen}
      schema={$schema.data}
      {namespace}
      name={datasetName}
    />
    <DownloadModal bind:open={downloadOpen} schema={$schema.data} />
  {/if}
</Page>
<Commands />

<style>
  .schema-container {
    transition: width 0.2s ease-in-out;
  }
</style>
