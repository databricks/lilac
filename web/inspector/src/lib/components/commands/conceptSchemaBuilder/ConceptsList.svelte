<script lang="ts">
  import {queryConcepts} from '$lib/queries/conceptQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {isColumn, type ConceptInfo, type ConceptScoreSignal, type LilacSchemaField} from '$lilac';

  export let field: LilacSchemaField;
  export let splitter: string | undefined;
  export let embedding: string;

  const CONCEPT_SCORE_ALIAS = 'concept_score_alias';

  const datasetViewStore = getDatasetViewContext();

  const concepts = queryConcepts();

  function selectConcept(concept: ConceptInfo) {
    // Remove existing concept_score column
    $datasetViewStore.queryOptions.columns = $datasetViewStore.queryOptions.columns?.filter(
      c => !isColumn(c) || c.alias !== CONCEPT_SCORE_ALIAS
    );

    // Add the udf column
    datasetViewStore.addUdfColumn({
      signal_udf: {
        namespace: concept.namespace,
        concept_name: concept.name,
        embedding: embedding as ConceptScoreSignal['embedding'],
        signal_name: 'concept_score',
        split: splitter as ConceptScoreSignal['split']
      },
      path: field.path,
      alias: CONCEPT_SCORE_ALIAS
    });

    // Ensure the concept_score column is visible
    if (splitter) datasetViewStore.addVisibleColumn([...field.path, splitter, '*']);
    datasetViewStore.addVisibleColumn([CONCEPT_SCORE_ALIAS]);
  }

  // Infer selected concept from the udf columns in the query options
  $: selectedConcept = $datasetViewStore.queryOptions.columns
    ?.filter(isColumn)
    .find(c => c.alias === CONCEPT_SCORE_ALIAS)?.signal_udf as ConceptScoreSignal;
</script>

{#if $concepts.isSuccess}
  <div class="flex flex-col border border-b-0 border-gray-200">
    {#each $concepts.data as concept}
      {@const selected =
        selectedConcept?.concept_name == concept.name &&
        selectedConcept?.namespace == concept.namespace}
      <button
        on:click={() => selectConcept(concept)}
        class="border-b border-gray-200 p-4 text-left"
        class:bg-blue-50={selected}
      >
        {concept.namespace} / {concept.name}
      </button>
    {/each}
  </div>
{/if}
