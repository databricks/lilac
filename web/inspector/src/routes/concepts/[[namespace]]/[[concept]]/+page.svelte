<script lang="ts">
  import {page} from '$app/stores';
  import ConceptView from '$lib/components/concepts/ConceptView.svelte';
  import {queryConcept, queryConcepts} from '$lib/queries/conceptQueries';
  import {SkeletonText} from 'carbon-components-svelte';

  $: namespace = $page.params.namespace;
  $: conceptName = $page.params.concept;

  const concepts = queryConcepts();
  $: concept = namespace && conceptName ? queryConcept(namespace, conceptName) : undefined;
</script>

<div class="flex h-full w-full">
  <div class=" h-full w-72 border-r border-gray-200">
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
    {/if}
  </div>
  <div class="h-full w-full p-4">
    {#if $concept?.isLoading}
      <SkeletonText />
    {:else if $concept?.isError}
      <p>{$concept.error.message}</p>
    {:else if $concept?.isSuccess}
      <ConceptView concept={$concept.data} />
    {/if}
  </div>
</div>
