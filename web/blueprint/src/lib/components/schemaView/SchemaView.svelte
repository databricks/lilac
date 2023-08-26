<script lang="ts">
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {SkeletonText} from 'carbon-components-svelte';
  import SchemaField from './SchemaField.svelte';

  const datasetStore = getDatasetContext();
  $: selectRowsSchema = $datasetStore.selectRowsSchema;
</script>

<div class="schema flex h-full flex-col overflow-y-auto">
  {#if selectRowsSchema?.isLoading}
    <SkeletonText paragraph lines={3} />
  {:else if selectRowsSchema?.isSuccess && selectRowsSchema.data.schema.fields != null}
    {#each Object.keys(selectRowsSchema.data.schema.fields) as key (key)}
      <SchemaField
        schema={selectRowsSchema.data.schema}
        field={selectRowsSchema.data.schema.fields[key]}
      />
    {/each}
  {/if}
</div>

<style>
  :global(.schema .bx--tab-content) {
    padding: 0 !important;
  }
</style>
