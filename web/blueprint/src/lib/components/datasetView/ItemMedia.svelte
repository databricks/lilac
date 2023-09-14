<script lang="ts">
  import {querySettings} from '$lib/queries/datasetQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  /**
   * Component that renders a single value from a row in the dataset row view
   * In the case of strings with string_spans, it will render the derived string spans as well
   */
  import {notEmpty} from '$lib/utils';
  import {displayPath, getComputedEmbeddings, getSpanValuePaths} from '$lib/view_utils';
  import {
    L,
    formatValue,
    getValueNodes,
    pathIsEqual,
    type LilacField,
    type LilacValueNode,
    type Path
  } from '$lilac';
  import StringSpanHighlight from './StringSpanHighlight.svelte';

  export let path: Path;
  export let row: LilacValueNode;
  export let field: LilacField;
  export let highlightedFields: LilacField[];

  const datasetViewStore = getDatasetViewContext();
  const datasetStore = getDatasetContext();

  $: computedEmbeddings = getComputedEmbeddings($datasetStore.schema, path);

  $: spanValuePaths = getSpanValuePaths(field, highlightedFields);

  $: settings = querySettings($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: valueNodes = getValueNodes(row, path);
</script>

{#each valueNodes as valueNode}
  {@const value = L.value(valueNode)}
  {#if notEmpty(value)}
    {@const path = L.path(valueNode) || []}
    {@const markdown = $settings.data?.ui?.markdown_paths?.find(p => pathIsEqual(p, path)) != null}
    <div class="flex">
      <div class="relative flex w-44 flex-none font-mono font-medium text-neutral-500">
        <div class="sticky top-0 self-start truncate p-4">
          {displayPath(path)}
        </div>
      </div>

      <div class="mx-4 w-full font-normal">
        <StringSpanHighlight
          text={formatValue(value)}
          {row}
          {path}
          {markdown}
          spanPaths={spanValuePaths.spanPaths}
          valuePaths={spanValuePaths.valuePaths}
          {datasetViewStore}
          datasetStore={$datasetStore}
          embeddings={computedEmbeddings}
        />
      </div>
    </div>
  {/if}
{/each}
