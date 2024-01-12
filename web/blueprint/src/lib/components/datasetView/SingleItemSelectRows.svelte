<script lang="ts">
  import {querySelectRows, querySelectRowsSchema} from '$lib/queries/datasetQueries';
  import {
    getDatasetViewContext,
    getSelectRowsOptions,
    getSelectRowsSchemaOptions
  } from '$lib/stores/datasetViewStore';
  import {ROWID, type SelectRowsResponse} from '$lilac';
  export let limit: number;
  export let rowsResponse: SelectRowsResponse | undefined = undefined;

  const store = getDatasetViewContext();

  $: selectRowsSchema = querySelectRowsSchema(
    $store.namespace,
    $store.datasetName,
    getSelectRowsSchemaOptions($store)
  );
  $: selectOptions = getSelectRowsOptions($store, true /* implicitSortByRowID */);
  $: rowsQuery = querySelectRows(
    $store.namespace,
    $store.datasetName,
    {
      ...selectOptions,
      columns: [ROWID],
      limit,
      // Sort by ROWID on top of any other sort_by option to ensure that the result order is stable.
      sort_by: [...(selectOptions.sort_by || []), ROWID]
    },
    $selectRowsSchema.data?.schema
  );

  $: {
    if (
      $rowsQuery != null &&
      $rowsQuery.data != null &&
      !$rowsQuery.isPreviousData &&
      !$rowsQuery.isFetching
    ) {
      rowsResponse = $rowsQuery.data;
    } else {
      rowsResponse = undefined;
    }
  }
</script>
