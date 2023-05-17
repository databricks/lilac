<script lang="ts">
  import {page} from '$app/stores';
  import Commands, {Command, triggerCommand} from '$lib/components/commands/Commands.svelte';
  import ConceptView from '$lib/components/concepts/ConceptView.svelte';
  import {queryConcept, queryConcepts} from '$lib/queries/conceptQueries';
  import type {Concept} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import AddAlt from 'carbon-icons-svelte/lib/AddAlt.svelte';

  $: namespace = $page.params.namespace;
  $: conceptName = $page.params.concept;

  const concepts = queryConcepts();
  $: concept = namespace && conceptName ? queryConcept(namespace, conceptName) : undefined;

  // If a concept doesn't exist, create a concept client side
  $: upsertedConcept =
    $concept?.isError && $concept.error.status === 404 ? createConcept() : undefined;

  function createConcept(): Concept {
    return {
      namespace: $page.params.namespace,
      concept_name: $page.params.concept,
      data: {},
      type: 'text'
    };
  }
</script>

<div class="flex h-full w-full">
  <div class="flex h-full w-72 flex-col border-r border-gray-200">
    {#if $concepts.isLoading}
      <SkeletonText />
    {:else if $concepts.isSuccess}
      {#each $concepts.data as c}
        <a
          href="/concepts/{c.namespace}/{c.name}"
          class="flex w-full flex-row items-center whitespace-pre border-b border-gray-200 px-4 py-2 hover:bg-gray-100"
          class:bg-blue-100={c.name === conceptName}
          class:hover:bg-blue-100={c.name === conceptName}
        >
          <span class="opacity-50">{c.namespace} / </span><span> {c.name}</span>
        </a>
      {/each}

      {#if upsertedConcept}
        <a
          href="/concepts/{upsertedConcept.namespace}/{upsertedConcept.concept_name}"
          class="flex w-full flex-row items-center whitespace-pre border-b border-gray-200 px-4 py-2 hover:bg-gray-100"
          class:bg-blue-100={upsertedConcept.concept_name === conceptName}
          class:hover:bg-blue-100={upsertedConcept.concept_name === conceptName}
        >
          <span class="opacity-50">{upsertedConcept.namespace} / </span><span>
            {upsertedConcept.concept_name}</span
          >
        </a>
      {/if}

      <button
        on:click={() => triggerCommand({command: Command.CreateConcept})}
        class="mt-4 flex w-full items-center gap-x-1 px-4 py-2 text-left text-sm text-gray-500 hover:text-blue-500"
        ><AddAlt /> Add Concept</button
      >
    {/if}
  </div>
  <div class="h-full w-full p-4">
    {#if $concept?.isLoading}
      <SkeletonText />
    {:else if $concept?.isError}
      {#if upsertedConcept}
        <ConceptView concept={upsertedConcept} />
      {:else}
        <p>{$concept.error.message}</p>
      {/if}
    {:else if $concept?.isSuccess}
      <ConceptView concept={$concept.data} />
    {/if}
  </div>
</div>

<Commands />
