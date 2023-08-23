<script lang="ts">
  import {goto} from '$app/navigation';
  import Page from '$lib/components/Page.svelte';
  import {hoverTooltip} from '$lib/components/common/HoverTooltip';
  import RowView from '$lib/components/datasetView/RowView.svelte';
  import SearchPanel from '$lib/components/datasetView/SearchPanel.svelte';
  import SchemaView from '$lib/components/schemaView/SchemaView.svelte';
  import {queryConfig, queryDatasetSchema} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {datasetLink} from '$lib/utils';
  import {Modal, SkeletonText, Tag, TextArea} from 'carbon-components-svelte';
  import {Download, Information, Settings, Share, TableOfContents} from 'carbon-icons-svelte';
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

  let configModalOpen = false;
  $: config = configModalOpen ? queryConfig(namespace, datasetName, 'yaml') : null;
</script>

<Page>
  <div slot="header-subtext" class="flex flex-row items-center gap-x-1">
    <button
      class="mr-2"
      class:bg-blue-100={!schemaCollapsed}
      class:outline-blue-400={!schemaCollapsed}
      class:outline={!schemaCollapsed}
      use:hoverTooltip={{text: schemaCollapsed ? 'Show Schema' : 'Hide Schema'}}
      on:click={toggleSchemaCollapsed}
      on:keypress={toggleSchemaCollapsed}><TableOfContents /></button
    >
    <Tag type="outline">
      <div class="dataset-name">
        <a class="font-semibold text-black" href={link} on:click={() => goto(link)}
          >{$datasetViewStore.namespace}/{$datasetViewStore.datasetName}
        </a>
      </div>
    </Tag>
    <button
      on:click={() => (configModalOpen = true)}
      use:hoverTooltip={{text: 'Dataset information'}}
    >
      <Information />
    </button>
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
          <button
            use:hoverTooltip={{text: 'Copy the URL'}}
            on:click={() =>
              navigator.clipboard.writeText(location.href).then(
                () => {
                  showCopyToast = true;
                  setTimeout(() => (showCopyToast = false), 2000);
                },
                () => {
                  throw Error('Error copying link to clipboard.');
                }
              )}><Share /></button
          >
        </div>

        <button use:hoverTooltip={{text: 'Download data'}} on:click={() => (downloadOpen = true)}
          ><Download /></button
        >
        <div
          use:hoverTooltip={{
            text: !canUpdateSettings
              ? 'User does not have access to update settings of this dataset.'
              : ''
          }}
          class:opacity-40={!canUpdateSettings}
          class="mr-2"
        >
          <button
            use:hoverTooltip={{text: 'Dataset settings'}}
            disabled={!canUpdateSettings}
            on:click={() => (settingsOpen = true)}><Settings /></button
          >
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

  {#if configModalOpen}
    <Modal
      open
      modalHeading="Dataset config"
      primaryButtonText="Ok"
      secondaryButtonText="Cancel"
      on:click:button--secondary={() => (configModalOpen = false)}
      on:close={() => (configModalOpen = false)}
      on:submit={() => (configModalOpen = false)}
    >
      <div class="mb-4 text-sm">
        This dataset configuration represents the transformations that created the dataset,
        including signals, embeddings, and user settings. This can be used with lilac.load to
        generate the dataset with the same view as presented.
      </div>
      <div class="font-mono text-xs">config.yml</div>
      {#if $config?.isFetching}
        <SkeletonText />
      {:else if $config?.data}
        <TextArea
          value={`${$config.data}`}
          readonly
          rows={15}
          placeholder="3 rows of data for previewing the response"
          class="mb-2 font-mono"
        />
      {/if}
    </Modal>
  {/if}
</Page>

<style lang="postcss">
  .schema-container {
    transition: width 0.2s ease-in-out;
  }
  .dataset-name {
    @apply truncate text-ellipsis;
    max-width: 8rem;
  }
</style>
