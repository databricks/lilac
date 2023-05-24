<script lang="ts">
  import {queryDatasetSchema} from '$lib/queries/datasetQueries';
  import {querySignals} from '$lib/queries/signalQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getField, listFields, type Path, type TextEmbeddingSignal} from '$lilac';
  import {Select, SelectItem} from 'carbon-components-svelte';
  import type {JSONSchema7} from 'json-schema';
  import {getContext} from 'svelte';
  import type {Writable} from 'svelte/store';

  export let rootValue: {split: string};
  export let invalid: boolean;
  export let invalidText: string;
  export let value: string;

  const datasetViewStore = getDatasetViewContext();
  const signals = querySignals();
  const schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);

  // Get the current field from the context, set by the CommandSignals component
  const field = getContext<Writable<Path>>('SIGNAL_FIELD_PATH');

  // Find the embedding signal json schema field
  $: embeddingSignalField = $signals.data?.find(s => s.name === 'concept_score')?.json_schema
    .properties?.embedding as JSONSchema7 | undefined;

  // Read the split value from the root value
  $: split = rootValue['split'];

  // Find all existing pre-computed embeddings for the current split from the schema
  $: existingEmbeddings =
    $field && $schema.data
      ? listFields(getField($schema.data, $field)).filter(
          f => f.dtype === 'embedding' && (f.signal as TextEmbeddingSignal).split == split
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

  // Warn if no embeddings are computed for this split
  $: anyEmbeddingsComputed = sortedEnum.some(
    embedding =>
      existingEmbeddings?.some(f => f.signal?.signal_name === embedding?.toString()) || false
  );
</script>

<Select
  labelText="Embedding *"
  warn={!anyEmbeddingsComputed}
  warnText="No embeddings pre-computed for this split"
  bind:selected={value}
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
