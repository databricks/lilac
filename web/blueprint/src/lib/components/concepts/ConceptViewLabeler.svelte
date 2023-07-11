<script lang="ts">
  import {editConceptMutation} from '$lib/queries/conceptQueries';
  import {querySelectRows} from '$lib/queries/datasetQueries';
  import {stringSlice} from '$lib/view_utils';
  import {
    UUID_COLUMN,
    formatValue,
    type Concept,
    type ConceptLabelsSignal,
    type ConceptQuery,
    type ConceptScoreSignal,
    type ExampleIn,
    type LilacSchema
  } from '$lilac';
  import {Button, InlineLoading, SkeletonText} from 'carbon-components-svelte';
  import {ThumbsDownFilled, ThumbsUpFilled} from 'carbon-icons-svelte';
  import {getCandidates} from './labeler_utils';

  export let dataset: {namespace: string; name: string};
  export let concept: Concept;
  export let fieldPath: string[];
  export let schema: LilacSchema;
  export let embedding: string;

  const NUM_ROW_CANDIDATES_TO_FETCH = 100;

  const conceptEdit = editConceptMutation();

  let votes: Record<number, boolean> = {};

  $: conceptQuery = {
    type: 'concept',
    concept_namespace: concept.namespace,
    concept_name: concept.concept_name,
    embedding: embedding
  } as ConceptQuery;

  $: topRows = querySelectRows(
    dataset.namespace,
    dataset.name,
    {
      columns: [fieldPath],
      limit: NUM_ROW_CANDIDATES_TO_FETCH,
      combine_columns: true,
      searches: [
        {
          path: fieldPath,
          query: conceptQuery
        }
      ]
    },
    schema
  );
  $: conceptSignal = {
    signal_name: 'concept_score',
    namespace: concept.namespace,
    concept_name: concept.concept_name,
    embedding
  } as ConceptScoreSignal;
  $: labelsSignal = {
    signal_name: 'concept_labels',
    namespace: concept.namespace,
    concept_name: concept.concept_name
  } as ConceptLabelsSignal;

  $: randomRows = querySelectRows(
    dataset.namespace,
    dataset.name,
    {
      columns: [
        fieldPath,
        {path: fieldPath, signal_udf: conceptSignal},
        {path: fieldPath, signal_udf: labelsSignal}
      ],
      limit: NUM_ROW_CANDIDATES_TO_FETCH,
      combine_columns: true,
      sort_by: [UUID_COLUMN] // Sort by UUID to get random rows.
    },
    schema
  );

  $: candidates = getCandidates(
    $topRows.data?.rows,
    $randomRows.data?.rows,
    concept,
    fieldPath,
    embedding
  );

  function addLabel(index: number, label: boolean) {
    votes[index] = label;
  }

  function submit() {
    const examplesIn: ExampleIn[] = Object.entries(votes).map(([i, label]) => {
      const candidate = candidates[parseInt(i)];
      const text = stringSlice(candidate.text, candidate.span.start, candidate.span.end);
      return {text, label};
    });
    $conceptEdit.mutate([concept.namespace, concept.concept_name, {insert: examplesIn}], {
      onSuccess: () => (votes = {})
    });
  }

  function getBackground(score: number): string {
    if (score < 0.2) {
      return 'bg-red-500/10';
    }
    if (score < 0.8) {
      return 'bg-yellow-500/10';
    }
    return 'bg-blue-500/10';
  }

  function getInfo(score: number): string {
    if (score < 0.2) {
      return 'Likely negative';
    }
    if (score < 0.8) {
      return 'Uncertain';
    }
    return 'Likely positive';
  }
</script>

{#if $topRows.isFetching || $randomRows.isFetching}
  <SkeletonText paragraph />
{:else}
  <div class="flex flex-col gap-y-4">
    {#each candidates as candidate, i}
      {@const background = getBackground(candidate.score)}
      {@const info = getInfo(candidate.score)}
      <div
        class={`flex flex-grow items-center rounded-md border border-gray-300 p-4 pl-2 ${background}`}
      >
        <div class="mr-2 flex flex-shrink-0 gap-x-1">
          <button
            class="p-2 hover:bg-gray-200"
            class:text-blue-500={votes[i] === true}
            on:click={() => addLabel(i, true)}
          >
            <ThumbsUpFilled />
          </button>
          <button
            class="p-2 hover:bg-gray-200"
            class:text-red-500={votes[i] === false}
            on:click={() => addLabel(i, false)}
          >
            <ThumbsDownFilled />
          </button>
        </div>
        <div class="flex-grow">
          {stringSlice(candidate.text, candidate.span.start, candidate.span.end)}
        </div>
        <div class="w-36 flex-shrink-0 text-right">{info} {formatValue(candidate.score, 2)}</div>
      </div>
    {/each}
    <Button icon={$conceptEdit.isLoading ? InlineLoading : undefined} on:click={submit}>
      Submit
    </Button>
  </div>
{/if}
