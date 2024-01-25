<script lang="ts">
  import {goto} from '$app/navigation';
  import Page from '$lib/components/Page.svelte';
  import {hoverTooltip} from '$lib/components/common/HoverTooltip';
  import ScrollView from '$lib/components/datasetView/ScrollView.svelte';
  import SearchPanel from '$lib/components/datasetView/SearchPanel.svelte';
  import SchemaView from '$lib/components/schemaView/SchemaView.svelte';
  import {queryDatasetSchema, querySettings} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {datasetLink} from '$lib/utils';
  import {
    CLUSTER_CATEGORY_FIELD,
    CLUSTER_TITLE_FIELD,
    childFields,
    isClusterRootField
  } from '$lilac';
  import {ComposedModal, ModalBody, ModalFooter, ModalHeader, Tag} from 'carbon-components-svelte';
  import {EdgeCluster, Export, Settings, Share, TableOfContents} from 'carbon-icons-svelte';
  import {fade} from 'svelte/transition';
  import ComputeClusterModal from '../ComputeClusterModal.svelte';
  import DatasetPivotViewer from './DatasetPivotViewer.svelte';
  import DatasetSettingsModal from './DatasetSettingsModal.svelte';
  import ExportModal from './ExportModal.svelte';
  import SingleItemView from './SingleItemView.svelte';
  import Insights from './insights/Insights.svelte';

  export let namespace: string;
  export let datasetName: string;

  const datasetViewStore = getDatasetViewContext();

  $: settingsQuery = querySettings(namespace, datasetName);
  $: itemsViewType = $settingsQuery.data?.ui?.view_type || 'single_item';

  $: schemaCollapsed = $datasetViewStore.schemaCollapsed;
  function toggleSchemaCollapsed() {
    $datasetViewStore.schemaCollapsed = !$datasetViewStore.schemaCollapsed;
  }

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: settingsOpen = $datasetViewStore.modal === 'Settings';
  $: exportOpen = $datasetViewStore.modal === 'Export';

  const authInfo = queryAuthInfo();
  $: canUpdateSettings = $authInfo.data?.access.dataset.update_settings;

  let showCopyToast = false;

  $: link = datasetLink(namespace, datasetName);

  // Determine whether the dataset has clusters.
  $: clusterFields = childFields($schema.data).filter(f => isClusterRootField(f));
  // For now, choose the first cluster.
  $: clusterField = clusterFields && clusterFields.length > 0 ? clusterFields[0] : null;
  $: clusterOuterPath = clusterField ? [...clusterField.path, CLUSTER_CATEGORY_FIELD] : null;
  $: clusterInnerPath = clusterField ? [...clusterField.path, CLUSTER_TITLE_FIELD] : null;
  $: clusterLink =
    clusterOuterPath != null && clusterInnerPath != null
      ? datasetLink($datasetViewStore.namespace, $datasetViewStore.datasetName, {
          ...$datasetViewStore,
          viewPivot: true,
          query: {filters: undefined, searches: undefined},
          groupBy: undefined,
          rowId: undefined,
          pivot: {outerPath: clusterOuterPath, innerPath: clusterInnerPath}
        })
      : null;
  $: clusterToggleLink = $datasetViewStore.viewPivot ? link : clusterLink;
</script>

<Page>
  <div slot="header-subtext" class="flex flex-row items-center gap-x-2">
    <Tag type="outline">
      <div class="dataset-name">
        <a class="font-semibold text-black" href={link} on:click={() => goto(link)}
          >{$datasetViewStore.namespace}/{$datasetViewStore.datasetName}
        </a>
      </div>
    </Tag>
    <button
      class:bg-blue-100={!schemaCollapsed}
      class:outline-blue-400={!schemaCollapsed}
      class:outline={!schemaCollapsed}
      use:hoverTooltip={{text: schemaCollapsed ? 'Show Schema' : 'Hide Schema'}}
      on:click={toggleSchemaCollapsed}
      on:keypress={toggleSchemaCollapsed}><TableOfContents /></button
    >
    <a href={clusterToggleLink} class="text-black">
      <button
        class:disabled={clusterField == null}
        class:cursor-default={clusterField == null}
        class:opacity-30={clusterField == null}
        class:bg-blue-100={$datasetViewStore.viewPivot}
        class:outline-blue-400={$datasetViewStore.viewPivot}
        class:outline={$datasetViewStore.viewPivot}
        use:hoverTooltip={{
          text:
            clusterField == null
              ? 'Clusters have not been computed for this dataset.'
              : !$datasetViewStore.viewPivot
              ? 'Open clusters'
              : 'Back to items'
        }}
      >
        <EdgeCluster /></button
      >
    </a>
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

        <button
          use:hoverTooltip={{text: 'Export data'}}
          on:click={() => ($datasetViewStore.modal = 'Export')}
        >
          <Export />
        </button>
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
            on:click={() => ($datasetViewStore.modal = 'Settings')}><Settings /></button
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
    <div class="h-full w-2/3 flex-grow py-1">
      {#if $datasetViewStore.viewPivot}
        <DatasetPivotViewer />
      {:else if itemsViewType == 'scroll'}
        <ScrollView />
      {:else if itemsViewType == 'single_item'}
        <SingleItemView modalOpen={$datasetViewStore.modal != null} />
      {/if}
    </div>
  </div>

  {#if $schema.data}
    <DatasetSettingsModal
      open={settingsOpen}
      {namespace}
      name={datasetName}
      on:close={() => ($datasetViewStore.modal = null)}
    />
    <ExportModal
      open={exportOpen}
      schema={$schema.data}
      on:close={() => ($datasetViewStore.modal = null)}
    />
    <ComposedModal
      size="lg"
      open={$datasetViewStore.insightsOpen}
      on:close={() => datasetViewStore.setInsightsOpen(false)}
      on:submit={() => datasetViewStore.setInsightsOpen(false)}
    >
      <ModalHeader title="Insights" />
      <ModalBody>
        {#if $datasetViewStore.insightsOpen}
          <Insights schema={$schema.data} {namespace} {datasetName} />
        {/if}
      </ModalBody>
      <ModalFooter primaryButtonText="Close" />
    </ComposedModal>
  {/if}

  <ComputeClusterModal />
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
