<script lang="ts">
  /**
   * Component that renders a single value from a row in the dataset row view
   * In the case of strings with string_spans, it will render the derived string spans as well
   */
  import {querySelectRowsSchema} from '$lib/queries/datasetQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext, getSelectRowsOptions} from '$lib/stores/datasetViewStore';

  import {notEmpty} from '$lib/utils';
  import {getVisibleFields} from '$lib/view_utils';
  import {
    L,
    formatValue,
    getValueNodes,
    isOrdinal,
    listFieldParents,
    pathIsEqual,
    type LilacSchema,
    type LilacValueNode,
    type Path
  } from '$lilac';
  import StringSpanHighlight from './StringSpanHighlight.svelte';

  export let path: Path;
  export let row: LilacValueNode;
  export let schema: LilacSchema;

  let datasetViewStore = getDatasetViewContext();
  let datasetStore = getDatasetContext();

  $: selectOptions = getSelectRowsOptions($datasetViewStore);

  $: selectRowsSchema = selectOptions
    ? querySelectRowsSchema(
        $datasetViewStore.namespace,
        $datasetViewStore.datasetName,
        selectOptions
      )
    : undefined;

  $: valueNodes = getValueNodes(row, path);
  $: field = L.field(valueNodes[0]);

  $: parents = field ? listFieldParents(field, schema) : undefined;
  $: dtype = valueNodes.length && L.dtype(valueNodes[0]);
  $: showValue =
    valueNodes.length && // Hide if there are no values
    dtype && // Hide if dtype is not set
    (isOrdinal(dtype) || dtype == 'string') && // Hide if dtype is not ordinal or string
    !parents?.some(parent => parent.dtype === 'string_span'); // Hide if any parent is a string span

  $: values = valueNodes.map(v => L.value(v)).filter(notEmpty);

  // If type is a string, figure out if there are any children that are string_span
  // Only do this if the column is visible, and it isn't a repeated field
  $: visibleFields = getVisibleFields($datasetViewStore, $datasetStore, field);

  $: stringSpanFields =
    showValue && field && dtype === 'string' && valueNodes.length === 1
      ? getVisibleFields($datasetViewStore, $datasetStore, field, 'string_span')
      : [];

  // Only find the 'keyword' searches for keyword search, since this is displayed differently.
  $: keywordSearchSpanFields =
    $datasetViewStore && $datasetViewStore.queryOptions.searches
      ? visibleFields.filter(field => {
          const searchResults = $selectRowsSchema?.data?.search_results || [];
          for (const [i, searchResult] of searchResults.entries()) {
            if (pathIsEqual(field.path, searchResult.result_path)) {
              return ($datasetViewStore.queryOptions.searches || [])[i].query.type === 'keyword';
            }
          }
          return false;
        })
      : [];
</script>

{#if showValue}
  <div class="flex flex-col">
    <div class="font-mono text-sm text-gray-600">
      {path.join('.')}
    </div>

    <div>
      <StringSpanHighlight
        text={formatValue(values[0])}
        {stringSpanFields}
        {keywordSearchSpanFields}
        {row}
      />
    </div>
  </div>
{/if}
