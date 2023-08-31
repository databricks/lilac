<script lang="ts">
  import {goto} from '$app/navigation';
  import {maybeQueryDatasetSchema} from '$lib/queries/datasetQueries';
  import {createDatasetViewStore} from '$lib/stores/datasetViewStore';
  import {datasetLink} from '$lib/utils';
  import {serializePath, type Concept, type LilacSchema} from '$lilac';
  import {Button, ToastNotification} from 'carbon-components-svelte';
  import {ArrowUpRight} from 'carbon-icons-svelte';
  import DatasetFieldEmbeddingSelector from '../DatasetFieldEmbeddingSelector.svelte';
  import ConceptDataFeeder from './ConceptDataFeeder.svelte';

  export let concept: Concept;

  let dataset: {namespace: string; name: string} | undefined | null = undefined;
  let schema: LilacSchema | null | undefined;
  let path: string[] | undefined;
  let embedding: string | undefined = undefined;

  $: schemaQuery = maybeQueryDatasetSchema(dataset?.namespace, dataset?.name);

  $: schema = $schemaQuery.data;
  $: pathId = path ? serializePath(path) : undefined;

  $: datasetViewStore =
    dataset != null && path != null && embedding != null
      ? createDatasetViewStore(dataset.namespace, dataset.name)
      : null;

  function openDataset() {
    if (
      pathId == null ||
      embedding == null ||
      dataset == null ||
      datasetViewStore == null ||
      $datasetViewStore == null
    ) {
      return;
    }

    datasetViewStore.addSearch({
      path: [pathId],
      type: 'concept',
      concept_namespace: concept.namespace,
      concept_name: concept.concept_name,
      embedding
    });
    goto(datasetLink(dataset.namespace!, dataset.name!, $datasetViewStore));
  }
</script>

<div class="flex flex-col gap-y-4">
  <div class="flex flex-row gap-x-4">
    <div class="flex-grow">
      <DatasetFieldEmbeddingSelector bind:dataset bind:path bind:embedding />
    </div>
    {#if pathId != null && embedding != null}
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
