<script lang="ts">
  import {queryDatasetSchema} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {childFields, getComputedEmbeddings, getField} from '$lilac';
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
  $: embeddingSchema = $ctx.jsonSchema?.properties?.embedding as JSONSchema7 | undefined;

  // Find all existing pre-computed embeddings for the current split from the schema
  $: precomputedEmbs =
    $ctx.path && $schema.data
      ? getComputedEmbeddings(getField($schema.data, $ctx.path)!)
      : undefined;

  $: $schema.data != null && $ctx.path != null
    ? console.log(childFields(getField($schema.data, $ctx.path)).map(f => f.dtype))
    : [];
  $: console.log('precomputed:', precomputedEmbs);
  $: console.log('embedding schema:', embeddingSchema);

  // Sort possible embeddings by if they are already computed
  $: sortedEnum = [...(embeddingSchema?.enum || [])].sort((a, b) => {
    const aComputed = precomputedEmbs?.some(f => f.signal?.signal_name === a?.toString());
    const bComputed = precomputedEmbs?.some(f => f.signal?.signal_name === b?.toString());
    if (aComputed && !bComputed) return -1;
    if (!aComputed && bComputed) return 1;
    return 0;
  });
  $: console.log('sorted:', sortedEnum);

  // The initial selected value should be the first computed embedding by default.
  $: {
    if (precomputedEmbs?.length && precomputedEmbs[0].signal?.signal_name) {
      value = precomputedEmbs[0].signal.signal_name;
    }
  }

  function selectionChanged(e: Event) {
    value = (e.target as HTMLInputElement).value;
  }

  // Check if the current value is computed
  $: computed = precomputedEmbs?.some(f => f.signal?.signal_name === value?.toString()) || false;

  // Create warn text if the current value is not computed
  $: warnText = !computed ? 'Embedding not pre-computed for this split' : undefined;
</script>

<Select
  on:change={selectionChanged}
  hideLabel={true}
  selected={value}
  warn={!!warnText}
  {warnText}
  {invalid}
  {invalidText}
>
  {#each sortedEnum as embedding}
    {@const computed = precomputedEmbs?.some(f => f.signal?.signal_name === embedding?.toString())}
    <SelectItem value={embedding?.toString()} text={embedding?.toString()} disabled={!computed} />
  {/each}
</Select>
