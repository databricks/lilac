<script lang="ts">
  import {querySelectRowsSchema} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext, getSelectRowsSchemaOptions} from '$lib/stores/datasetViewStore';
  import {SkeletonText} from 'carbon-components-svelte';
  import SchemaField from './SchemaField.svelte';

  const datasetViewStore = getDatasetViewContext();
  $: selectRowsSchema = querySelectRowsSchema(
    $datasetViewStore.namespace,
    $datasetViewStore.datasetName,
    getSelectRowsSchemaOptions($datasetViewStore)
  );
</script>

<div class="schema flex h-full flex-col overflow-y-auto">
  {#if $selectRowsSchema?.isLoading}
    <SkeletonText paragraph lines={3} />
  {:else if $selectRowsSchema?.isSuccess && $selectRowsSchema.data.schema.fields != null}
    {#each Object.keys($selectRowsSchema.data.schema.fields) as key (key)}
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
