<script lang="ts">
  import {editConceptMutation} from '$lib/queries/conceptQueries';
  import {querySelectRows} from '$lib/queries/datasetQueries';
  import type {Concept, ExampleIn, LilacSchema} from '$lilac';
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

  $: rows = querySelectRows(
    dataset.namespace,
    dataset.name,
    {
      columns: [fieldPath],
      limit: NUM_ROW_CANDIDATES_TO_FETCH,
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
  $: candidates = getCandidates($rows.data?.rows, concept, fieldPath, embedding);

  function addLabel(index: number, label: boolean) {
    votes[index] = label;
  }

  function submit() {
    const examplesIn: ExampleIn[] = Object.entries(votes).map(([i, label]) => ({
      text: candidates[parseInt(i)].text,
      label
    }));
    $conceptEdit.mutate([concept.namespace, concept.concept_name, {insert: examplesIn}], {
      onSuccess: () => (votes = {})
    });
  }
</script>

{#if $rows.isFetching}
  <SkeletonText paragraph />
{:else}
  <div class="flex flex-col gap-y-4">
    {#each candidates as candidate, i}
      <div class="flex items-center rounded-md border border-gray-300 p-4 pl-2">
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
        <div class="flex-grow">{candidate.text}</div>
      </div>
    {/each}
    <Button icon={$conceptEdit.isLoading ? InlineLoading : undefined} on:click={submit}>
      Submit
    </Button>
  </div>
{/if}
