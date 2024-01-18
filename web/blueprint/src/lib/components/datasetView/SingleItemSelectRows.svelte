<script lang="ts">
  import {querySelectRows, querySelectRowsSchema} from '$lib/queries/datasetQueries';
  import {
    getDatasetViewContext,
    getSelectRowsOptions,
    getSelectRowsSchemaOptions
  } from '$lib/stores/datasetViewStore';
  import {L, ROWID, type SelectRowsResponse} from '$lilac';
  export let limit: number;
  export let offset: number | undefined = undefined;
  export let rowsResponse: SelectRowsResponse | undefined = undefined;
  export let lookAheadRowId: string | null = null;

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
      limit: limit + 1,
      offset,
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
      rowsResponse = {
        total_num_rows: $rowsQuery.data.total_num_rows,
        rows: $rowsQuery.data.rows.slice(0, -1)
      };
      lookAheadRowId = L.value(
        $rowsQuery.data.rows[$rowsQuery.data.rows.length - 1][ROWID],
        'string'
      );
    } else {
      rowsResponse = undefined;
      lookAheadRowId = null;
    }
  }
</script>
