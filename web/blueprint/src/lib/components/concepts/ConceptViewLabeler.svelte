<script lang="ts">
  import {querySelectRows} from '$lib/queries/datasetQueries';
  import type {Concept, LilacSchema} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import {ThumbsDownFilled, ThumbsUpFilled} from 'carbon-icons-svelte';
  import {getCandidates} from './labeler_utils';

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
      limit: 100,
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

  function addLabel(text: string, label: boolean) {
    console.log(text, label);
  }
</script>

{#if $rows.isLoading}
  <SkeletonText paragraph />
{:else}
  <div class="flex flex-col gap-y-4">
    {#each candidates as candidate}
      <div class="flex items-center rounded-md border border-gray-300 p-4 pl-2">
        <div class="mr-2 flex flex-shrink-0 gap-x-1">
          <button class="p-2 hover:bg-gray-200" on:click={() => addLabel(candidate.text, true)}>
            <ThumbsUpFilled />
          </button>
          <button class="p-2 hover:bg-gray-200" on:click={() => addLabel(candidate.text, false)}>
            <ThumbsDownFilled />
          </button>
        </div>
        <div class="flex-grow">{candidate.text}</div>
      </div>
    {/each}
  </div>
{/if}
