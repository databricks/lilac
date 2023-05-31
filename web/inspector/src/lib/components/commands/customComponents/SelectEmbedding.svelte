<script lang="ts">
  import {queryDatasetSchema} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getField, listFields} from '$lilac';
  import {Select, SelectItem} from 'carbon-components-svelte';
  import type {JSONSchema7} from 'json-schema';
  import {getCommandSignalContext} from '../CommandSignals.svelte';

  export let invalid: boolean;
  export let invalidText: string;
  export let value: string;

  const datasetViewStore = getDatasetViewContext();
  const schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);

  // Get the current field from the context, set by the CommandSignals component
  const ctx = getCommandSignalContext();

  // Find the embedding signal json schema field
  $: embeddingSignalField = $ctx.jsonSchema?.properties?.embedding as JSONSchema7 | undefined;

  // Find all existing pre-computed embeddings for the current split from the schema
  $: existingEmbeddings =
    $ctx.path && $schema.data
      ? listFields(getField($schema.data, $ctx.path)).filter(
          f => f.signal != null && listFields(f).some(f => f.dtype === 'embedding')
        )
      : undefined;

  // Sort possible embeddings by if they are already computed
  $: sortedEnum = [...(embeddingSignalField?.enum || [])].sort((a, b) => {
    const aComputed = existingEmbeddings?.some(f => f.signal?.signal_name === a?.toString());
    const bComputed = existingEmbeddings?.some(f => f.signal?.signal_name === b?.toString());
    if (aComputed && !bComputed) return -1;
    if (!aComputed && bComputed) return 1;
    return 0;
  });

  // Make the initial selected value by the first computed embedding.
  $: value = sortedEnum[0]?.toString() || '';

  // Check if the current value is computed
  $: computed = existingEmbeddings?.some(f => f.signal?.signal_name === value?.toString()) || false;

  // Create warn text if the current value is not computed
  $: warnText = !computed ? 'Embedding not pre-computed for this split' : undefined;
</script>

<Select
  labelText="Embedding *"
  bind:selected={value}
  warn={!!warnText}
  {warnText}
  {invalid}
  {invalidText}
>
  {#each sortedEnum as embedding}
    {@const computed = existingEmbeddings?.some(
      f => f.signal?.signal_name === embedding?.toString()
    )}
    <SelectItem value={embedding?.toString()} text={embedding?.toString()} disabled={!computed} />
  {/each}
</Select>
