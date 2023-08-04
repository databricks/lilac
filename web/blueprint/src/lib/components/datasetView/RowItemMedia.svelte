<script lang="ts">
  import {querySettings} from '$lib/queries/datasetQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  /**
   * Component that renders a single value from a row in the dataset row view
   * In the case of strings with string_spans, it will render the derived string spans as well
   */
  import {notEmpty} from '$lib/utils';
  import {getComputedEmbeddings, getSearchPath, getSpanValuePaths} from '$lib/view_utils';
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

  const datasetViewStore = getDatasetViewContext();
  const datasetStore = getDatasetContext();
  $: visibleFields = $datasetStore.visibleFields || [];
  $: searchPath = getSearchPath($datasetViewStore, $datasetStore);
  $: computedEmbeddings = getComputedEmbeddings($datasetStore, searchPath);

  $: spanValuePaths = getSpanValuePaths(field, visibleFields);

  $: settings = querySettings($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: values = getValueNodes(row, path)
    .map(v => L.value(v))
    .filter(notEmpty);
</script>

{#each values as value, i}
  {@const suffix = values.length > 1 ? `[${i}]` : ''}
  {@const markdown = $settings.data?.ui?.markdown_paths?.find(p => pathIsEqual(p, path)) != null}
  <div class="flex flex-row">
    <div class="flex w-full flex-col">
      <div
        class="sticky top-0 z-10 w-full self-start border-t border-neutral-200 bg-neutral-100 px-2 py-2
               pb-2 font-mono font-medium text-neutral-500"
      >
        {path.join('.') + suffix}
      </div>

      <div class="mx-4 font-normal">
        <StringSpanHighlight
          text={formatValue(value)}
          {row}
          {markdown}
          spanPaths={spanValuePaths.spanPaths}
          valuePaths={spanValuePaths.valuePaths}
          {datasetViewStore}
          datasetStore={$datasetStore}
          embeddings={computedEmbeddings}
        />
      </div>
    </div>
  </div>
{/each}
