<script lang="ts">
  import {querySelectRowsSchema} from '$lib/queries/datasetQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext, getSelectRowsOptions} from '$lib/stores/datasetViewStore';
  /**
   * Component that renders a single value from a row in the dataset row view
   * In the case of strings with string_spans, it will render the derived string spans as well
   */
  import {notEmpty} from '$lib/utils';
  import {getVisibleFields} from '$lib/view_utils';
  import {
    L,
    formatValue,
    getValueNodes,
    isOrdinal,
    listFieldParents,
    pathIncludes,
    pathIsEqual,
    type LilacSchema,
    type LilacValueNode,
    type Path
  } from '$lilac';
  import StringSpanHighlight from './StringSpanHighlight.svelte';

  export let path: Path;
  export let row: LilacValueNode;
  export let searchResultsPaths: Path[];
  export let schema: LilacSchema;
  export let aliasMapping: Record<string, Path> | undefined;

  let datasetViewStore = getDatasetViewContext();
  let datasetStore = getDatasetContext();

  $: selectOptions = getSelectRowsOptions($datasetViewStore);

  // TODO(nsthorat): Move this into the dataset store.
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

  // For string fields, find the derived search span fields.
  $: keywordSearchSpanFields = visibleFields
    .filter(field =>
      // Enables search results to be highlighted.
      searchResultsPaths.some(searchPath => pathIncludes(field.path, searchPath))
    )
    .filter(field => {
      if ($datasetViewStore == null || $datasetViewStore.queryOptions.searches == null) {
        return false;
      }
      for (const [i, searchResultPath] of $selectRowsSchema?.data?.searchResultsPaths.entries() ||
        []) {
        if (pathIsEqual(field.path, searchResultPath)) {
          const search = $datasetViewStore.queryOptions.searches[i];
          return search.type === 'contains';
        }
      }
      return false;
    });
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
