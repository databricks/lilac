<script lang="ts">
  import {querySelectRows, querySelectRowsSchema} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext, getSelectRowsSchemaOptions} from '$lib/stores/datasetViewStore';
  import {DELETED_LABEL_KEY, ROWID, formatValue} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import {TrashCan, View} from 'carbon-icons-svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import RestoreRowsButton from '../datasetView/RestoreRowsButton.svelte';
  import SchemaField from './SchemaField.svelte';

  const datasetViewStore = getDatasetViewContext();
  $: selectRowsSchema = querySelectRowsSchema(
    $datasetViewStore.namespace,
    $datasetViewStore.datasetName,
    getSelectRowsSchemaOptions($datasetViewStore)
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
</script>

<div class="schema flex h-full flex-col overflow-y-auto">
  <!-- Deleted rows. -->
  {#if numDeletedRows}
    <div
      class="flex w-full flex-row items-center justify-between gap-x-2 border-b border-gray-300 bg-red-500 bg-opacity-10 p-2 px-4"
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
          on:click={() => datasetViewStore.showTrash(!$datasetViewStore.viewTrash)}><View /></button
        >
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

<style>
  :global(.schema .bx--tab-content) {
    padding: 0 !important;
  }
</style>
