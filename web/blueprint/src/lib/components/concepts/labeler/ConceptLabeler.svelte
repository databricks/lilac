<script lang="ts">
  import {goto} from '$app/navigation';
  import {maybeQueryDatasetSchema} from '$lib/queries/datasetQueries';
  import {createDatasetViewStore} from '$lib/stores/datasetViewStore';
  import {getNavigationContext} from '$lib/stores/navigationStore';
  import {datasetLink} from '$lib/utils';
  import type {Concept, LilacSchema} from '$lilac';
  import {Button, ToastNotification} from 'carbon-components-svelte';
  import {ArrowUpRight} from 'carbon-icons-svelte';
  import {get} from 'svelte/store';
  import DatasetFieldEmbeddingSelector from '../DatasetFieldEmbeddingSelector.svelte';
  import ConceptDataFeeder from './ConceptDataFeeder.svelte';

  export let concept: Concept;

  let dataset: {namespace: string; name: string} | undefined | null = undefined;
  let schema: LilacSchema | null | undefined;
  let path: string[] | undefined;
  let embedding: string | undefined = undefined;
  const navState = getNavigationContext();

  $: schemaQuery =
    dataset?.namespace && dataset?.name
      ? maybeQueryDatasetSchema(dataset.namespace, dataset.name)
      : null;

  $: schema = $schemaQuery?.data;

  function openDataset() {
    if (path == null || embedding == null || dataset == null) {
      return;
    }
    const store = createDatasetViewStore(dataset.namespace, dataset.name);
    store.addSearch({
      path,
      type: 'concept',
      concept_namespace: concept.namespace,
      concept_name: concept.concept_name,
      embedding
    });
    goto(datasetLink(dataset.namespace, dataset.name, $navState, get(store)));
  }
</script>

<div class="flex flex-col gap-y-4">
  <div class="flex flex-row gap-x-4">
    <div class="flex-grow">
      <DatasetFieldEmbeddingSelector bind:dataset bind:path bind:embedding />
    </div>
    {#if path != null && embedding != null}
      <Button
        class="dataset-link top-7 h-8"
        icon={ArrowUpRight}
        iconDescription={'Open dataset and apply concept.'}
        on:click={openDataset}
      />
    {/if}
  </div>

  {#if dataset != null && path != null && schema != null && embedding != null}
    <div>
      <ConceptDataFeeder {concept} {dataset} fieldPath={path} {schema} {embedding} />
    </div>
  {/if}
  {#if embedding == null}
    <ToastNotification
      hideCloseButton
      kind="warning"
      fullWidth
      lowContrast
      title="No embeddings"
      caption={'Dataset has no fields with computed embeddings. ' +
        'Please compute an embedding index before using the labeler on this dataset.'}
    />
  {/if}
</div>

<style lang="postcss">
  :global(.dataset-link.bx--btn) {
    @apply min-h-0;
  }
</style>
