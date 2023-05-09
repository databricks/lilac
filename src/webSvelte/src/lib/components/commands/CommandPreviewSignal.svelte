<script lang="ts">
  import {useGetSchemaQuery} from '$lib/store/apiDataset';
  import {getDatasetViewContext} from '$lib/store/datasetViewStore';
  import {
    ENTITY_FEATURE_KEY,
    listFields,
    type Column,
    type ConceptInfo,
    type ConceptScoreSignal,
    type SignalTransform
  } from '$lilac';
  import {
    Button,
    ComposedModal,
    InlineNotification,
    ModalBody,
    ModalFooter,
    ModalHeader
  } from 'carbon-components-svelte';
  import {createEventDispatcher} from 'svelte';
  import {Command, triggerCommand, type PreviewConceptCommand} from './Commands.svelte';
  import ConceptSelect from './selectors/ConceptSelect.svelte';
  import FieldSelect from './selectors/FieldSelect.svelte';

  export let command: PreviewConceptCommand;

  let path = command.path;
  let concept: ConceptInfo;

  const dispatch = createEventDispatcher();

  $: schema = useGetSchemaQuery(command.namespace, command.datasetName);

  $: hasEmbeddingField =
    $schema.isSuccess && listFields($schema.data).some(field => field.dtype == 'embedding');

  const datsetViewStore = getDatasetViewContext();

  function submit() {
    const signal: ConceptScoreSignal = {
      signal_name: 'concept_score',
      namespace: concept.namespace,
      concept_name: concept.name,
      embedding_name: 'cohere'
    };

    const transform: SignalTransform = {signal};
    const conceptColumn: Column = {
      feature: path,
      transform
    };

    datsetViewStore.addExtraColumn(conceptColumn);
    close();
  }

  function close() {
    dispatch('close');
  }
</script>

<ComposedModal open on:submit={submit} on:close={close}>
  <ModalHeader label="Concepts" title="Preview concept" />
  <ModalBody hasForm>
    <div class="flex flex-col gap-y-8">
      {#if !hasEmbeddingField}
        <div>
          <InlineNotification
            lowContrast
            kind="info"
            title="No Embeddings"
            subtitle="Compute an embedding field first to preview concepts"
          />
          <Button
            kind="tertiary"
            on:click={() =>
              triggerCommand({
                command: Command.ComputeSignal,
                namespace: command.namespace,
                datasetName: command.datasetName,
                signalName: 'cohere'
              })}>Compute Embedding</Button
          >
        </div>
      {:else}
        <FieldSelect
          filter={field => field.dtype == 'embedding' && field.path.at(-1) == ENTITY_FEATURE_KEY}
          bind:path
          labelText="Field"
          helperText="Select embedding field to use"
        />
      {/if}

      <ConceptSelect bind:concept />
    </div>
  </ModalBody>
  <ModalFooter
    primaryButtonText="Preview"
    secondaryButtonText="Cancel"
    primaryButtonDisabled={!concept || !path}
    on:click:button--secondary={close}
  />
</ComposedModal>
