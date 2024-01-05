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

  // When defined, allows the caller to specify the select rows options. When not defined, defaults
  // to the select rows options from the store.
  export let selectRowsOptions: SelectRowsOptions | undefined = undefined;

  const store = getDatasetViewContext();

  $: selectRowsSchema = querySelectRowsSchema(
    $store.namespace,
    $store.datasetName,
    getSelectRowsSchemaOptions($store)
  );
  $: selectOptions =
    selectRowsOptions || getSelectRowsOptions($store, true /* implicitSortByRowID */);
  $: rowsQuery = querySelectRows(
    $store.namespace,
    $store.datasetName,
    {...selectOptions, columns: [ROWID], limit},
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
