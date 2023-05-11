<script lang="ts">
  import {
    queryDatasetManifest,
    queryDatasetSchema,
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

  $: selectOptions = $schema.isSuccess
    ? getSelectRowsOptions($datasetViewStore, $schema.data)
    : undefined;

  // Get the resulting schmema including UDF columns
  $: selectRowsSchema = selectOptions
    ? querySelectRowsSchema(
        $datasetViewStore.namespace,
        $datasetViewStore.datasetName,
        selectOptions
      )
    : undefined;
</script>

<div class="flex flex-col gap-y-4 py-4">
  <div class="flex w-full justify-between px-4">
    <Breadcrumb noTrailingSlash skeleton={$schema.isLoading}>
      <BreadcrumbItem href="/">datasets</BreadcrumbItem>
      <BreadcrumbItem href="/">{$datasetViewStore.namespace}</BreadcrumbItem>
      <BreadcrumbItem>{$datasetViewStore.datasetName}</BreadcrumbItem>
    </Breadcrumb>

    {#if $manifest.isSuccess}
      ({$manifest.data.dataset_manifest.num_items.toLocaleString()}
    {/if}
    rows)
  </div>

  {#if $selectRowsSchema?.isLoading}
    <SkeletonText paragraph lines={3} />
  {:else if $selectRowsSchema?.isSuccess && $selectRowsSchema.data.fields}
    <Tabs>
      <Tab label="Schema" />
      <Tab label="Raw Query" />
      <svelte:fragment slot="content">
        <TabContent>
          {#each Object.keys($selectRowsSchema.data.fields) as key (key)}
            <SchemaField
              schema={$selectRowsSchema.data}
              field={$selectRowsSchema.data.fields[key]}
            />
          {/each}
        </TabContent>
        <TabContent>
          <QueryBuilder />
        </TabContent>
      </svelte:fragment>
    </Tabs>
  {/if}
</div>

<style>
  :global(.bx--tab-content) {
    padding: 0;
  }
</style>
