<script lang="ts">
  import {useGetConceptsQuery} from '$lib/store/apiConcept';
  import type {ConceptInfo} from '$lilac';
  import {
    StructuredList,
    StructuredListBody,
    StructuredListCell,
    StructuredListHead,
    StructuredListInput,
    StructuredListRow,
    StructuredListSkeleton
  } from 'carbon-components-svelte';
  import CheckmarkFilled from 'carbon-icons-svelte/lib/CheckmarkFilled.svelte';

  export let concept: ConceptInfo | undefined = undefined;

  const concepts = useGetConceptsQuery();

  let selectedConceptString: string | undefined;

  $: concept =
    $concepts.data?.find(c => `${c.namespace}/${c.name}` === selectedConceptString) ?? concept;
</script>

{#if $concepts.isSuccess}
  <StructuredList selection required bind:selected={selectedConceptString} label="Signal">
    <StructuredListHead>
      <StructuredListRow head>
        <StructuredListCell head>Concept</StructuredListCell>
      </StructuredListRow>
    </StructuredListHead>
    <StructuredListBody>
      {#each $concepts.data as concept}
        <StructuredListRow label for={concept.name}>
          <StructuredListCell>{concept.namespace}/{concept.name}</StructuredListCell>
          <StructuredListInput id={concept.name} value="{concept.namespace}/{concept.name}" />
          <StructuredListCell>
            <CheckmarkFilled
              class="bx--structured-list-svg"
              aria-label="select an option"
              title="select an option"
            />
          </StructuredListCell>
        </StructuredListRow>
      {/each}
    </StructuredListBody>
  </StructuredList>
{:else if $concepts.isLoading}
  <StructuredListSkeleton rows={5} />
{/if}
