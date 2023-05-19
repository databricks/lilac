<script lang="ts">
  import {queryDatasetSchema} from '$lib/queries/datasetQueries';
  import {querySignals} from '$lib/queries/signalQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {
    deserializePath,
    getField,
    isSignalField,
    listFields,
    pathIsEqual,
    serializePath,
    type LilacSchemaField
  } from '$lilac';
  import {InlineNotification, Select, SelectItem, SelectSkeleton} from 'carbon-components-svelte';
  import type {JSONSchema} from 'json-schema-library';
  import ConceptsList from './ConceptsList.svelte';
  import SemanticSearch from './SemanticSearch.svelte';

  const datasetViewStore = getDatasetViewContext();

  let selectedField: LilacSchemaField | undefined = undefined;
  let selectedSplitter: string | undefined = 'sentences';
  let selectedEmbedding: string | undefined = undefined;

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);
  $: signals = querySignals();

  $: {
    // Find all viusible non-signal columns
    const visibleNonSignalColumns = $datasetViewStore.visibleColumns?.filter(p => {
      if (!$schema.data) return false;
      const field = $schema.data && getField($schema.data, p);
      return field && !isSignalField(field, $schema.data);
    });
    console.log(visibleNonSignalColumns);
    // If there is only one visible non-signal column, and nothing selected, select it
    if (!selectedField && $schema.isSuccess && visibleNonSignalColumns?.length == 1) {
      selectedField = getField($schema.data, $datasetViewStore.visibleColumns[0]);
    }
    // If the selected field is no longer visible, deselect it
    if (!visibleNonSignalColumns.some(p => pathIsEqual(p, selectedField?.path))) {
      selectedField = undefined;
    }
  }

  // Find the selected field's splitter field, or if no splitter the field itself
  $: selectedSplitterField = selectedSplitter
    ? selectedField?.fields?.[selectedSplitter].repeated_field
    : selectedField;

  // Find the selected field's embedding field
  $: selectedEmbeddingField = selectedEmbedding
    ? selectedSplitterField?.fields?.[selectedEmbedding]
    : undefined;

  // Find the concept_score signal info
  $: conceptScoreSignalInfo = $signals.isSuccess
    ? $signals.data.find(s => s.name === 'concept_score')
    : undefined;

  // Extract available splitters from the signal schema
  $: possibleSplitters = ((conceptScoreSignalInfo?.json_schema.properties?.split as JSONSchema)
    ?.enum || []) as string[];
  // Extract available embeddings from the signal schema
  $: possibleEmbeddings = ((conceptScoreSignalInfo?.json_schema.properties?.embedding as JSONSchema)
    ?.enum || []) as string[];

  function handleFieldChange(event: CustomEvent<string | number>) {
    const oldField = selectedField;

    const path = deserializePath(event.detail as string);
    if (path.length == 0 || !$schema.data) return;
    selectedField = getField($schema.data, path);

    // Show the new field
    datasetViewStore.addVisibleColumn(path);
    // Hide the old field
    if (oldField) datasetViewStore.removeVisibleColumn(oldField.path);
  }
</script>

<div class="flex gap-x-4 p-4">
  <!-- Field selector -->
  {#if $schema?.isLoading}
    <SelectSkeleton />
  {:else if $schema.isError}
    <InlineNotification kind="error" title="Error" subtitle={$schema.error.message} />
  {:else if $schema?.isSuccess}
    <Select
      labelText="Field"
      on:update={handleFieldChange}
      helperText="Field to visualize concepts on"
      selected={selectedField ? serializePath(selectedField.path) : ''}
    >
      {#if $datasetViewStore.visibleColumns.length != 1}
        <SelectItem value="" text="Select a field" disabled />
      {/if}

      {#each listFields($schema.data) as field}
        {#if !isSignalField(field, $schema.data) && field.dtype === 'string'}
          <SelectItem value={serializePath(field.path)} text={serializePath(field.path)} />
        {/if}
      {/each}
    </Select>
  {/if}

  <!-- Splitter selector -->
  <Select labelText="Text Splitter" helperText="Splitter to use" bind:selected={selectedSplitter}>
    <SelectItem value={undefined} text={'none'} />
    {#each possibleSplitters as splitter}
      <SelectItem value={splitter} text={splitter} />
    {/each}
  </Select>

  <!-- Embedding selector -->
  <Select labelText="Embedding" helperText="Embedding to use" bind:selected={selectedEmbedding}>
    {#each possibleEmbeddings as embedding}
      <SelectItem value={embedding} text={embedding} />
    {/each}
  </Select>
</div>

<div class="p-4">
  {#if selectedField && !selectedEmbeddingField}
    Embedding not computed
    <!-- TODO make ui to trigger computation -->
  {:else if selectedField && selectedEmbedding}
    <div class="flex flex-col gap-y-4">
      <SemanticSearch
        field={selectedField}
        splitter={selectedSplitter}
        embedding={selectedEmbedding}
      />

      <ConceptsList
        field={selectedField}
        splitter={selectedSplitter}
        embedding={selectedEmbedding}
      />
    </div>
  {/if}
</div>
