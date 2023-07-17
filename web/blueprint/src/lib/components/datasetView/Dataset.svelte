<script lang="ts">
  import Page from '$lib/components/Page.svelte';
  import Commands from '$lib/components/commands/Commands.svelte';
  import {hoverTooltip} from '$lib/components/common/HoverTooltip';
  import RowView from '$lib/components/datasetView/RowView.svelte';
  import SearchPanel from '$lib/components/datasetView/SearchPanel.svelte';
  import SchemaView from '$lib/components/schemaView/SchemaView.svelte';
  import {
    queryDatasetSchema,
    queryManyDatasetStats,
    querySelectRowsSchema
  } from '$lib/queries/datasetQueries';
  import {createDatasetStore, setDatasetContext, type StatsInfo} from '$lib/stores/datasetStore';
  import {
    createDatasetViewStore,
    getSelectRowsSchemaOptions,
    setDatasetViewContext
  } from '$lib/stores/datasetViewStore';
  import {getVisibleFields} from '$lib/view_utils';
  import {getFieldsByDtype} from '$lilac';
  import {Button, Tag} from 'carbon-components-svelte';
  import {ChevronLeft, ChevronRight, Download, Reset} from 'carbon-icons-svelte';

  export let namespace: string;
  export let datasetName: string;

  $: datasetViewStore = createDatasetViewStore(namespace, datasetName);
  $: setDatasetViewContext(datasetViewStore);

  $: schemaCollapsed = $datasetViewStore.schemaCollapsed;
  function toggleSchemaCollapsed() {
    $datasetViewStore.schemaCollapsed = !$datasetViewStore.schemaCollapsed;
  }

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);
  $: stringFields = getFieldsByDtype('string', $schema.data);
  $: stats = queryManyDatasetStats(
    stringFields.map(f => {
      return [
        $datasetViewStore.namespace,
        $datasetViewStore.datasetName,
        {
          leaf_path: f.path
        }
      ];
    })
  );

  // Get the resulting schema including UDF columns
  $: selectRowsSchema = querySelectRowsSchema(
    $datasetViewStore.namespace,
    $datasetViewStore.datasetName,
    getSelectRowsSchemaOptions($datasetViewStore)
  );

  const datasetStore = createDatasetStore(namespace, datasetName);
  setDatasetContext(datasetStore);

  // Compute the stats for all string fields and write them to the dataset store. This allows us to
  // share stats about fields with all children.
  let sortedStats: StatsInfo[] | null = null;
  $: {
    if (
      $schema.data != null &&
      $stats.length > 0 &&
      !$stats.some(stat => stat == null || stat.isLoading)
    ) {
      sortedStats = $stats
        .map((stats, i) => ({path: stringFields[i].path, stats}))
        .sort((a, b) => {
          if (a == null || b == null) {
            return 0;
          }
          return (b.stats.data?.avg_text_length || 0) - (a.stats.data?.avg_text_length || 0);
        });
    }
  }

  $: {
    if ($schema.data != null) {
      datasetStore.setSchema($schema.data);
    }
  }
  $: {
    if ($selectRowsSchema != null) {
      datasetStore.setSelectRowsSchema($selectRowsSchema);
    }
  }
  $: {
    if (sortedStats != null) {
      datasetStore.setStats(sortedStats);
    }
  }
  $: {
    const visibleFields = getVisibleFields(
      $datasetViewStore.selectedColumns,
      $selectRowsSchema?.data?.schema || null
    );
    datasetStore.setVisibleFields(visibleFields);
  }

  async function downloadSelectRows() {
    const namespace = $datasetViewStore.namespace;
    const datasetName = $datasetViewStore.datasetName;
    const options = $datasetViewStore.queryOptions;
    options.columns = $datasetStore.visibleFields?.map(x => x.path);
    const url =
      `/api/v1/datasets/${namespace}/${datasetName}/select_rows_download` +
      `?url_safe_options=${encodeURIComponent(JSON.stringify(options))}`;
    const link = document.createElement('a');
    link.download = `${namespace}_${datasetName}.json`;
    link.href = url;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }
</script>

<Page title={'Datasets'}>
  <div slot="header-subtext">
    <div
      use:hoverTooltip={{
        text: `${$datasetViewStore.namespace}/${$datasetViewStore.datasetName}`
      }}
    >
      <Tag type="outline">{$datasetViewStore.datasetName}</Tag>
    </div>
  </div>
  <div slot="header-center" class="flex w-full items-center">
    <SearchPanel />
  </div>
  <div slot="header-right">
    <div class="flex h-full flex-col">
      <div class="flex">
        <Button
          size="field"
          kind="ghost"
          icon={Reset}
          iconDescription="Reset View"
          on:click={datasetViewStore.reset}
        />
        <Button
          size="field"
          kind="ghost"
          icon={Download}
          iconDescription="Download selection"
          on:click={downloadSelectRows}
        />
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
      <div
        class={`absolute right-0 top-1/2 flex
                h-8 w-4 cursor-pointer items-center justify-center
                rounded border
                border-neutral-200 bg-neutral-100
                opacity-60 hover:bg-neutral-200
                hover:opacity-100
                ${schemaCollapsed ? ' translate-x-full' : ' translate-x-1/2'}`}
        use:hoverTooltip={{text: schemaCollapsed ? 'Show Schema' : 'Hide Schema'}}
        on:click={toggleSchemaCollapsed}
        on:keypress={toggleSchemaCollapsed}
      >
        {#if !schemaCollapsed}
          <ChevronLeft />
        {:else}
          <ChevronRight />
        {/if}
      </div>
    </div>
    <div class="h-full w-2/3 flex-grow"><RowView /></div>
  </div>
</Page>
<Commands />

<style>
  .schema-container {
    transition: width 0.2s ease-in-out;
  }
</style>
