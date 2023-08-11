<script lang="ts">
  import {editConceptMutation} from '$lib/queries/conceptQueries';
  import {querySelectRows} from '$lib/queries/datasetQueries';
  import {
    UUID_COLUMN,
    formatValue,
    type Concept,
    type ConceptLabelsSignal,
    type ConceptQuery,
    type ConceptSignal,
    type ExampleIn,
    type LilacSchema
  } from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import {ThumbsDownFilled, ThumbsUpFilled} from 'carbon-icons-svelte';
  import {getCandidates, type Candidate, type Candidates} from '../labeler_utils';

  export let dataset: {namespace: string; name: string};
  export let concept: Concept;
  export let fieldPath: string[];
  export let schema: LilacSchema;
  export let embedding: string;

  const NUM_ROW_CANDIDATES_TO_FETCH = 100;

  const conceptEdit = editConceptMutation();

  let prevCandidates: Candidates = {};
  let candidates: Candidates = {};

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
      columns: [UUID_COLUMN, fieldPath],
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
  } as ConceptSignal;
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
        UUID_COLUMN,
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
    prevCandidates,
    $topRows.isFetching ? undefined : $topRows.data?.rows,
    $randomRows.isFetching ? undefined : $randomRows.data?.rows,
    concept,
    fieldPath,
    embedding
  );
  $: candidateList = [candidates.positive, candidates.neutral, candidates.negative];

  function addLabel(candidate: Candidate | undefined, label: boolean) {
    if (candidate == null) {
      return;
    }
    const exampleIn: ExampleIn = {text: candidate.text, label};
    const key = Object.keys(candidates).find(
      key => candidates[key as keyof Candidates] === candidate
    );
    // Save the old state.
    prevCandidates = {...candidates};
    $conceptEdit.mutate([concept.namespace, concept.concept_name, {insert: [exampleIn]}], {
      onSuccess: () =>
        (prevCandidates = {
          ...prevCandidates,
          [key as keyof Candidates]: undefined
        })
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
      return 'Likely not in concept';
    }
    if (score < 0.8) {
      return 'Uncertain';
    }
    return 'Likely in concept';
  }
</script>

<div class="flex flex-col gap-y-4">
  {#each candidateList as candidate}
    {#if candidate == null}
      <SkeletonText paragraph lines={2} />
    {:else}
      {@const background = getBackground(candidate.score)}
      {@const info = getInfo(candidate.score)}
      <div
        class={`flex flex-grow items-center rounded-md border border-gray-300 p-4 pl-2 ${background}`}
      >
        <div class="mr-2 flex flex-shrink-0 gap-x-1">
          <button
            class="p-2 hover:bg-gray-200"
            class:text-blue-500={candidate.label === true}
            on:click={() => addLabel(candidate, true)}
          >
            <ThumbsUpFilled />
          </button>
          <button
            class="p-2 hover:bg-gray-200"
            class:text-red-500={candidate.label === false}
            on:click={() => addLabel(candidate, false)}
          >
            <ThumbsDownFilled />
          </button>
        </div>
        <div class="flex-grow">{candidate.text}</div>
        <div class="w-40 flex-shrink-0 text-right">{info} {formatValue(candidate.score, 2)}</div>
      </div>
    {/if}
  {/each}
</div>
