<script lang="ts">
  import {DEFAULT_SELECT_ROWS_LIMIT, querySelectRows} from '$lib/queries/datasetQueries';
  import type {Concept, LilacSchema} from '$lilac';

  export let dataset: {namespace: string; name: string};
  export let concept: Concept;
  export let fieldPath: string[];
  export let schema: LilacSchema;
  export let embedding: string;

  $: rows = querySelectRows(
    dataset.namespace,
    dataset.name,
    {
      columns: [fieldPath],
      limit: DEFAULT_SELECT_ROWS_LIMIT,
      combine_columns: true,
      searches: [
        {
          path: fieldPath,
          query: {
            type: 'concept',
            concept_namespace: concept.namespace,
            concept_name: concept.concept_name,
            embedding: embedding
          }
        }
      ]
    },
    schema
  );
  $: console.log($rows.data);
</script>

{JSON.stringify(dataset, null, 2)}
{fieldPath}
{embedding}
