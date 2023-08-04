<script lang="ts">
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {SkeletonText, Tab, TabContent, Tabs} from 'carbon-components-svelte';
  import QueryBuilder from '../queryBuilder/QueryBuilder.svelte';
  import FlattenedField from './FlattenedField.svelte';
  import SchemaField from './SchemaField.svelte';

  const datasetStore = getDatasetContext();

  $: selectRowsSchema = $datasetStore.selectRowsSchema;
</script>

<div class="schema flex h-full flex-col pt-4">
  <Tabs class="overflow-hidden border-b border-gray-200">
    <Tab label="Schema" class="w-1/3" />
    <Tab label="Tree View" class="w-1/3" />
    <Tab label="Raw Query" class="w-1/3" />
    <div class="h-full overflow-y-auto" slot="content">
      <TabContent>
        {#if selectRowsSchema?.isLoading}
          <SkeletonText paragraph lines={3} />
        {:else if selectRowsSchema?.isSuccess && selectRowsSchema.data.schema.fields != null}
          {#each Object.keys(selectRowsSchema.data.schema.fields) as key (key)}
            <FlattenedField
              schema={selectRowsSchema.data.schema}
              field={selectRowsSchema.data.schema.fields[key]}
            />
          {/each}
        {/if}
      </TabContent>
      <TabContent>
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
      </TabContent>
      <TabContent>
        <QueryBuilder />
      </TabContent>
    </div>
  </Tabs>
</div>

<style>
  :global(.schema .bx--tab-content) {
    padding: 0 !important;
  }
</style>
