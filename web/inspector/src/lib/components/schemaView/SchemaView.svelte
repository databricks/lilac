<script lang="ts">
  import {
    queryDatasetManifest,
    queryDatasetSchema,
    querySelectRowsAliasUdfPaths,
    querySelectRowsSchema
  } from '$lib/queries/datasetQueries';
  import {getDatasetViewContext, getSelectRowsOptions} from '$lib/stores/datasetViewStore';
  import {
    Breadcrumb,
    BreadcrumbItem,
    SkeletonText,
    Tab,
    TabContent,
    Tabs
  } from 'carbon-components-svelte';
  import QueryBuilder from '../queryBuilder/QueryBuilder.svelte';
  import SchemaField from './SchemaField.svelte';

  const datasetViewStore = getDatasetViewContext();
  const schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);
  const manifest = queryDatasetManifest($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: selectOptions = $schema.isSuccess ? getSelectRowsOptions($datasetViewStore) : undefined;

  // Get the resulting schmema including UDF columns
  $: selectRowsSchema = selectOptions
    ? querySelectRowsSchema(
        $datasetViewStore.namespace,
        $datasetViewStore.datasetName,
        selectOptions
      )
    : undefined;

  $: aliasMapping = selectOptions
    ? querySelectRowsAliasUdfPaths(
        $datasetViewStore.namespace,
        $datasetViewStore.datasetName,
        selectOptions
      )
    : undefined;
</script>

<div class="flex h-full flex-col pt-4">
  <div class="mb-4 flex w-full items-center justify-between gap-x-2 px-4">
    <Breadcrumb noTrailingSlash skeleton={$schema.isLoading}>
      <BreadcrumbItem href="/">datasets</BreadcrumbItem>
      <BreadcrumbItem href="/">{$datasetViewStore.namespace}</BreadcrumbItem>
      <BreadcrumbItem>{$datasetViewStore.datasetName}</BreadcrumbItem>
    </Breadcrumb>

    {#if $manifest.isSuccess}
      ({$manifest.data.dataset_manifest.num_items.toLocaleString()} rows)
    {/if}
    <button class="ml-auto border p-2 hover:bg-gray-100" on:click={datasetViewStore.reset}
      >Reset View</button
    >
  </div>

  <Tabs>
    <Tab label="Schema" />
    <Tab label="Raw Query" />
    <div class="h-full overflow-y-auto" slot="content">
      <TabContent>
        {#if $selectRowsSchema?.isLoading}
          <SkeletonText paragraph lines={3} />
        {:else if $selectRowsSchema?.isSuccess && $selectRowsSchema.data.fields}
          {#each Object.keys($selectRowsSchema.data.fields) as key (key)}
            <SchemaField
              schema={$selectRowsSchema.data}
              field={$selectRowsSchema.data.fields[key]}
              aliasMapping={$aliasMapping?.data}
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
