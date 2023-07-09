<script lang="ts">
  import {queryDatasetSchema} from '$lib/queries/datasetQueries';
  import {
    childFields,
    deserializePath,
    serializePath,
    type LilacField,
    type LilacSchema,
    type TextEmbeddingSignal
  } from '$lilac';
  import {InlineNotification, Select, SelectItem, SelectSkeleton} from 'carbon-components-svelte';

  export let dataset: {namespace: string; name: string};
  export let path: string[] | undefined;
  export let schema: LilacSchema | undefined = undefined;

  $: schemaQuery = queryDatasetSchema(dataset.namespace, dataset.name);
  $: schema = $schemaQuery.data;
  $: pathId = path ? serializePath(path) : undefined;
  $: indexedFields = childFields($schemaQuery.data).filter(
    f => f.signal != null && childFields(f).some(f => f.dtype === 'embedding')
  ) as LilacField<TextEmbeddingSignal>[];

  $: {
    // Auto-select the first field.
    if (indexedFields.length > 0 && path == null) {
      path = indexedFields[0].path;
    }
  }

  function fieldSelected(e: Event) {
    const val = (e.target as HTMLInputElement).value;
    path = deserializePath(val);
  }
</script>

{#if $schemaQuery.isLoading}
  <SelectSkeleton />
{:else if $schemaQuery.isError}
  <InlineNotification
    kind="error"
    title="Error"
    subtitle={$schemaQuery.error.message}
    hideCloseButton
  />
{:else}
  <Select labelText="Field" on:change={fieldSelected} selected={pathId}>
    {#each indexedFields as field}
      <SelectItem value={serializePath(field.path)} />
    {/each}
  </Select>
{/if}
