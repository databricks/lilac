<script lang="ts">
  import {queryDatasetManifest, queryDatasetSchema} from '$lib/queries/datasetQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {
    Breadcrumb,
    BreadcrumbItem,
    Button,
    SkeletonText,
    Tab,
    TabContent,
    Tabs
  } from 'carbon-components-svelte';
  import {Download, Reset} from 'carbon-icons-svelte';
  import QueryBuilder from '../queryBuilder/QueryBuilder.svelte';
  import FlattenedField from './FlattenedField.svelte';
  import SchemaField from './SchemaField.svelte';

  const datasetViewStore = getDatasetViewContext();
  const datasetStore = getDatasetContext();

  const schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);
  const manifest = queryDatasetManifest($datasetViewStore.namespace, $datasetViewStore.datasetName);

  // Get the resulting schmema including UDF columns
  $: selectRowsSchema = $datasetStore.selectRowsSchema;

  async function downloadSelectRows() {
    const namespace = $datasetViewStore.namespace;
    const datasetName = $datasetViewStore.datasetName;
    const options = $datasetViewStore.queryOptions;
    options.columns = Object.keys($datasetViewStore.selectedColumns).filter(
      k => $datasetViewStore.selectedColumns[k]
    );
    const url =
      `/api/v1/datasets/${namespace}/${datasetName}/select_rows_download` +
      `?options=${encodeURIComponent(JSON.stringify(options))}`;
    const link = document.createElement('a');
    link.download = `${namespace}_${datasetName}.json`;
    link.href = url;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }
</script>

<div class="flex h-full flex-col pt-4">
  <div class="mb-4 flex w-full items-center justify-between gap-x-2 px-4">
    <div class="flex items-center">
      <Breadcrumb noTrailingSlash skeleton={$schema.isLoading}>
        <BreadcrumbItem href="/">datasets</BreadcrumbItem>
        <BreadcrumbItem href="/">{$datasetViewStore.namespace}</BreadcrumbItem>
        <BreadcrumbItem>{$datasetViewStore.datasetName}</BreadcrumbItem>
      </Breadcrumb>

      {#if $manifest.isSuccess}
        ({$manifest.data.dataset_manifest.num_items.toLocaleString()} rows)
      {/if}
    </div>
    <div class="flex">
      <Button
        kind="ghost"
        icon={Reset}
        iconDescription="Reset View"
        on:click={datasetViewStore.reset}
      />
      <Button
        kind="ghost"
        icon={Download}
        iconDescription="Download selection"
        on:click={downloadSelectRows}
      />
    </div>
  </div>

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
  :global(.bx--tab-content) {
    padding: 0 !important;
  }
</style>
