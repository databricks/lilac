<script lang="ts">
  import {maybeQueryDatasetSchema, queryDatasets} from '$lib/queries/datasetQueries';
  import {getSettingsContext} from '$lib/stores/settingsStore';
  import {
    childFields,
    deserializePath,
    getField,
    isSignalField,
    serializePath,
    type LilacField,
    type LilacSchema
  } from '$lilac';
  import {InlineNotification, Select, SelectItem, SelectSkeleton} from 'carbon-components-svelte';

  export let dataset: {namespace: string; name: string} | undefined | null = undefined;
  export let path: string[] | undefined;
  export let embedding: string | undefined = undefined;

  const settings = getSettingsContext();

  let schema: LilacSchema | null | undefined;

  $: embeddingPriority = [$settings.embedding, 'gte-small', 'gte-base', 'openai', 'sbert'];

  const datasets = queryDatasets();
  $: schemaQuery = maybeQueryDatasetSchema(dataset?.namespace, dataset?.name);

  $: {
    // Auto-select the first dataset.
    if ($datasets.data && $datasets.data.length > 0 && dataset === undefined) {
      dataset = {namespace: $datasets.data[0].namespace, name: $datasets.data[0].dataset_name};
    }
  }

  $: datasetId = dataset ? `${dataset.namespace}/${dataset.name}` : '';

  $: schema = $schemaQuery.data;
  $: pathId = path ? serializePath(path) : undefined;
  $: sourceFields = schema
    ? childFields(schema).filter(f => !isSignalField(f) && f.dtype != null)
    : [];
  $: indexedFields = sourceFields.filter(f =>
    childFields(f).some(f => f.signal != null && childFields(f).some(f => f.dtype === 'embedding'))
  ) as LilacField[];

  $: embeddings =
    path && schema
      ? childFields(getField(schema, path)).filter(
          f => f.signal != null && childFields(f).some(f => f.dtype === 'embedding')
        )
      : [];

  $: embeddingNames = embeddings
    .map(a => a.signal!.signal_name)
    .sort((a, b) => {
      let aPriority = embeddingPriority.indexOf(a);
      let bPriority = embeddingPriority.indexOf(b);
      if (aPriority === -1) {
        aPriority = embeddingPriority.length;
      }
      if (bPriority === -1) {
        bPriority = embeddingPriority.length;
      }
      return aPriority - bPriority;
    });

  // Clear path if it is not in the list of indexed fields.
  $: {
    if (path != null) {
      const pathId = serializePath(path);
      const pathExists = indexedFields.some(f => serializePath(f.path) === pathId);
      if (!pathExists) {
        path = undefined;
      }
    }
  }

  // Clear embedding if it is not in the list of embeddings.
  $: {
    if (embedding != null) {
      const embeddingExists = embeddings.some(f => f.path.at(-1) === embedding);
      if (!embeddingExists) {
        embedding = undefined;
      }
    }
  }
  $: {
    // Auto-select the first field.
    if (indexedFields.length > 0 && path == null) {
      path = indexedFields[0].path;
    }
  }

  function datasetSelected(e: Event) {
    const val = (e.target as HTMLInputElement).value;
    if (val === '') {
      dataset = null;
    } else {
      const [namespace, name] = val.split('/');
      dataset = {namespace, name};
    }
  }

  function fieldSelected(e: Event) {
    const val = (e.target as HTMLInputElement).value;
    path = deserializePath(val);
  }
</script>

<div class="flex w-full flex-row gap-x-4">
  <div class="w-1/3">
    {#if $datasets.isLoading}
      <SelectSkeleton />
    {:else if $datasets.isError}
      <InlineNotification
        kind="error"
        title="Error"
        subtitle={$datasets.error.message}
        hideCloseButton
      />
    {:else if $datasets.data.length > 0}
      <Select labelText="Dataset" on:change={datasetSelected} selected={datasetId}>
        <SelectItem value="" text="none" />
        {#each $datasets.data as dataset}
          <SelectItem value={`${dataset.namespace}/${dataset.dataset_name}`} />
        {/each}
      </Select>
    {/if}
  </div>

  <div class="w-1/3">
    {#if $schemaQuery.isLoading}
      <SelectSkeleton />
    {:else if $schemaQuery.isError}
      <InlineNotification
        kind="error"
        title="Error"
        subtitle={$schemaQuery.error.message}
        hideCloseButton
      />
    {:else if indexedFields.length > 0}
      <Select labelText="Field with embeddings" on:change={fieldSelected} selected={pathId}>
        {#each indexedFields as field}
          <SelectItem value={serializePath(field.path)} />
        {/each}
      </Select>
    {/if}
  </div>
  <div class="w-1/3">
    {#if embeddingNames.length > 0}
      <Select labelText="Embedding" bind:selected={embedding}>
        {#each embeddingNames as embeddingName}
          <SelectItem value={embeddingName} />
        {/each}
      </Select>
    {/if}
  </div>
</div>

<style lang="postcss">
  :global(.dataset-link.bx--btn) {
    @apply min-h-0;
  }
</style>
