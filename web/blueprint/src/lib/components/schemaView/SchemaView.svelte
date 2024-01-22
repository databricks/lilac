<script lang="ts">
  import {
    queryConfig,
    queryDatasetSchema,
    querySelectRows,
    querySelectRowsSchema
  } from '$lib/queries/datasetQueries';
  import {getDatasetViewContext, getSelectRowsSchemaOptions} from '$lib/stores/datasetViewStore';
  import {DELETED_LABEL_KEY, ROWID, formatValue} from '$lilac';
  import {Modal, SkeletonText, TextArea} from 'carbon-components-svelte';
  import {Information, TrashCan, View, ViewOff} from 'carbon-icons-svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import RestoreRowsButton from '../datasetView/RestoreRowsButton.svelte';
  import SchemaField from './SchemaField.svelte';

  const datasetViewStore = getDatasetViewContext();
  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);
  $: selectRowsSchema = querySelectRowsSchema(
    $datasetViewStore.namespace,
    $datasetViewStore.datasetName,
    getSelectRowsSchemaOptions($datasetViewStore, $schema.data)
  );

  $: rowsQuery = querySelectRows(
    $datasetViewStore.namespace,
    $datasetViewStore.datasetName,
    {
      columns: [ROWID],
      limit: 1
    },
    $selectRowsSchema.data?.schema
  );

  $: hasDeletedLabel = Object.keys($selectRowsSchema.data?.schema?.fields || {}).includes(
    DELETED_LABEL_KEY
  );

  // Get the number of deleted rows.
  $: deletedCountQuery = hasDeletedLabel
    ? querySelectRows(
        $datasetViewStore.namespace,
        $datasetViewStore.datasetName,
        {
          columns: [ROWID],
          filters: [{path: DELETED_LABEL_KEY, op: 'exists'}],
          limit: 1,
          include_deleted: true
        },
        $selectRowsSchema.data?.schema
      )
    : null;
  $: numDeletedRows = $deletedCountQuery?.data?.total_num_rows;

  $: fieldKeys =
    $selectRowsSchema.data?.schema.fields != null
      ? // Remove the deleted label and the rowid from the schema fields.
        Object.keys($selectRowsSchema.data.schema.fields).filter(
          key => key !== DELETED_LABEL_KEY && key !== ROWID
        )
      : [];

  let configModalOpen = false;
  $: config = configModalOpen
    ? queryConfig($datasetViewStore.namespace, $datasetViewStore.datasetName, 'yaml')
    : null;
</script>

<div class="schema flex h-full flex-col overflow-y-auto">
  <!-- Dataset information -->
  <div
    class="flex w-full flex-row items-center justify-between gap-x-2 border-b border-gray-300 bg-neutral-300 bg-opacity-20 p-2 px-4"
  >
    <div class="flex flex-row items-center">
      {#if $rowsQuery.isFetching}
        <SkeletonText paragraph lines={1} />
      {:else if $rowsQuery.data?.rows != null}
        {formatValue($rowsQuery.data?.total_num_rows)} rows
      {/if}
    </div>
    <div>
      <button
        on:click={() => (configModalOpen = true)}
        use:hoverTooltip={{text: 'Dataset information'}}
      >
        <Information />
      </button>
    </div>
  </div>
  <!-- Deleted rows. -->
  {#if numDeletedRows}
    <div
      class="flex w-full flex-row items-center justify-between gap-x-2 border-b border-gray-300 bg-red-500 bg-opacity-20 p-2 px-4"
    >
      <div class="flex flex-row items-center gap-x-6">
        <div>
          <TrashCan />
        </div>
        <div class="font-medium">
          {formatValue(numDeletedRows)} deleted rows
        </div>
      </div>
      <div>
        <button
          use:hoverTooltip={{text: 'Show deleted rows'}}
          class="border border-gray-300 bg-white hover:border-gray-500"
          on:click={() => datasetViewStore.showTrash(!$datasetViewStore.viewTrash)}
        >
          {#if $datasetViewStore.viewTrash}
            <ViewOff />
          {:else}
            <View />
          {/if}
        </button>
        <RestoreRowsButton numRows={numDeletedRows} />
      </div>
    </div>
  {/if}
  {#if $selectRowsSchema?.isLoading}
    <SkeletonText paragraph lines={3} />
  {:else if $selectRowsSchema?.isSuccess && $selectRowsSchema.data.schema.fields != null}
    {#each fieldKeys as key (key)}
      <SchemaField
        schema={$selectRowsSchema.data.schema}
        field={$selectRowsSchema.data.schema.fields[key]}
      />
    {/each}
  {/if}
</div>

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
      This dataset configuration represents the transformations that created the dataset, including
      signals, embeddings, and user settings. This can be used with lilac.load to generate the
      dataset with the same view as presented.
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

<style>
  :global(.schema .bx--tab-content) {
    padding: 0 !important;
  }
</style>
