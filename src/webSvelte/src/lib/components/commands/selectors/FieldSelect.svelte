<script lang="ts">
  import {queryDatasetSchema} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {
    isSignalField,
    listFields,
    pathIsEqual,
    serializePath,
    type LilacSchemaField,
    type Path
  } from '$lilac';
  import {Select, SelectItem, SelectItemGroup, SelectSkeleton} from 'carbon-components-svelte';

  export let labelText = 'Field';
  export let helperText: string | undefined = undefined;
  export let filter: ((field: LilacSchemaField) => boolean) | undefined = undefined;

  export let defaultPath: Path | undefined = undefined;
  export let path: Path | undefined = undefined;

  const datasetViewStore = getDatasetViewContext();

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: fields = $schema.isSuccess
    ? listFields($schema.data)
        .filter(field => field.path.length > 0)
        .filter(field => (filter ? filter(field) : true))
    : null;

  $: sourceFields = fields?.filter(f => $schema.data && !isSignalField(f, $schema.data));
  $: signalFields = fields?.filter(f => $schema.data && isSignalField(f, $schema.data));

  function formatField(field: LilacSchemaField): string {
    return `${field.path.join('.')} (${field.dtype})`;
  }

  let selectedPath: string | undefined;

  // Set the selected index to the defaultPath if set
  $: {
    if (defaultPath && fields && !selectedPath) {
      const defaultSelection = fields.find(f => pathIsEqual(f.path, defaultPath));
      if (defaultSelection) {
        selectedPath = serializePath(defaultSelection.path);
      }
    }
  }

  // Set selectedPath to undefined if no valid fields are found
  $: {
    if (!fields?.length && $schema.isSuccess) {
      path = undefined;
    }
  }

  // Clear selectedPath if its not present in fields
  $: {
    if (fields && selectedPath) {
      const selectedField = fields.some(f => serializePath(f.path) === selectedPath);
      if (!selectedField) {
        selectedPath = serializePath(fields[0].path);
      }
    }
  }

  // Update path whenever selectedIndex changes
  $: {
    if (fields) {
      const selectedField = fields?.find(f => serializePath(f.path) === selectedPath);
      if (selectedField) {
        path = selectedField.path;
      }
    }
  }
</script>

{#if $schema.isLoading}
  <SelectSkeleton />
{:else if fields?.length === 0}
  <Select invalid invalidText="No valid fields found" />
{:else}
  <Select {labelText} {helperText} bind:selected={selectedPath} required>
    {#if sourceFields?.length}
      <SelectItemGroup label="Source Fields">
        {#each sourceFields as field}
          <SelectItem
            value={serializePath(field.path)}
            disabled={false}
            text={formatField(field)}
          />
        {/each}
      </SelectItemGroup>
    {/if}
    {#if signalFields?.length}
      <SelectItemGroup label="Signal Fields">
        {#each signalFields as field}
          <SelectItem
            value={serializePath(field.path)}
            disabled={false}
            text={formatField(field)}
          />
        {/each}
      </SelectItemGroup>
    {/if}
  </Select>
{/if}
