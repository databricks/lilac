<script lang="ts">
  import {DEFAULT_SELECT_ROWS_LIMIT, querySelectRows} from '$lib/queries/datasetQueries';
  import type {LilacSchema} from '$lilac';

  export let dataset: {namespace: string; name: string};
  export let path: string[];
  export let schema: LilacSchema;

  $: rows = querySelectRows(
    dataset.namespace,
    dataset.name,
    {columns: [path], limit: DEFAULT_SELECT_ROWS_LIMIT},
    schema
  );
  $: console.log($rows.data);
</script>

{JSON.stringify(dataset, null, 2)}
{path}
