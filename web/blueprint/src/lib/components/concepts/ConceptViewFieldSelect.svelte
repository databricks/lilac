<script lang="ts">
  import {queryDatasetSchema} from '$lib/queries/datasetQueries';
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

  export let dataset: {namespace: string; name: string};
  export let schema: LilacSchema | undefined = undefined;
  export let path: string[] | undefined;
  export let embedding: string | undefined = undefined;

  $: schemaQuery = queryDatasetSchema(dataset.namespace, dataset.name);
  $: schema = $schemaQuery.data;
  $: pathId = path ? serializePath(path) : undefined;
  $: sourceFields = childFields($schemaQuery.data).filter(
    f => !isSignalField(f, schema!) && f.dtype != null
  );
  $: indexedFields = sourceFields.filter(f =>
    childFields(f).some(f => f.signal != null && childFields(f).some(f => f.dtype === 'embedding'))
  ) as LilacField[];

  $: embeddings =
    path && schema
      ? childFields(getField(schema, path)).filter(
          f => f.signal != null && childFields(f).some(f => f.dtype === 'embedding')
        )
      : [];
  $: {
    if (path != null) {
      const pathId = serializePath(path);
      const pathExists = indexedFields.some(f => serializePath(f.path) === pathId);
      // Clear path if it is not in the list of indexed fields.
      if (!pathExists) {
        path = undefined;
      }
    }
  }

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
  <Select labelText="Field with embeddings" on:change={fieldSelected} selected={pathId}>
    {#each indexedFields as field}
      <SelectItem value={serializePath(field.path)} />
    {/each}
  </Select>
{/if}
{#if path}
  <Select labelText="Embedding" bind:selected={embedding}>
    {#each embeddings as embedding}
      <SelectItem value={embedding.path.at(-1)} />
    {/each}
  </Select>
{/if}
