<script lang="ts">
  import {computeSignalMutation} from '$lib/queries/datasetQueries';
  import {querySignals} from '$lib/queries/signalQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {conceptLink} from '$lib/utils';
  import {SIGNAL_INPUT_TYPE_TO_VALID_DTYPES, type ConceptInfo, type LilacField} from '$lilac';
  import {ComposedModal, ModalBody, ModalFooter, ModalHeader} from 'carbon-components-svelte';
  import {ArrowUpRight} from 'carbon-icons-svelte';
  import type {JSONSchema4Type} from 'json-schema';
  import type {JSONError} from 'json-schema-library';
  import {SvelteComponent, createEventDispatcher} from 'svelte';
  import SvelteMarkdown from 'svelte-markdown';
  import JsonSchemaForm from '../JSONSchema/JSONSchemaForm.svelte';
  import {createCommandSignalContext} from './CommandSignals.svelte';
  import type {ComputeConceptCommand} from './Commands.svelte';
  import SelectEmbedding from './customComponents/SelectEmbedding.svelte';
  import ConceptList from './selectors/ConceptList.svelte';
  import FieldSelect from './selectors/FieldSelect.svelte';

  export let command: ComputeConceptCommand;

  let path = command.path;
  let conceptPropertyValues: Record<string, JSONSchema4Type> = {
    signal_name: 'concept_score'
  };
  let errors: JSONError[] = [];

  let selectedConceptInfo: ConceptInfo;

  const signals = querySignals();
  $: signalInfo = $signals.data?.find(c => c.name === 'concept_score');

  // Store the field path and json schema in the context so custom components can access it
  const contextStore = createCommandSignalContext(path, signalInfo?.json_schema);
  $: $contextStore.path = path;
  $: $contextStore.jsonSchema = signalInfo?.json_schema;

  const datasetViewStore = getDatasetViewContext();
  const dispatch = createEventDispatcher();

  const signalMutation = computeSignalMutation();

  const customComponents: Record<string, Record<string, typeof SvelteComponent>> = {
    concept_score: {
      '/embedding': SelectEmbedding
    }
  };

  $: filterField = (field: LilacField) => {
    if (!field.dtype) return false;
    if (!signalInfo?.input_type) {
      return true;
    }
    const validDtypes = SIGNAL_INPUT_TYPE_TO_VALID_DTYPES[signalInfo.input_type];
    return validDtypes.includes(field.dtype);
  };

  function submit() {
    if (!signalInfo) return;
    if (path == null) return;
    if (selectedConceptInfo == null) return;

    const conceptSignal = {
      ...conceptPropertyValues,
      signal_name: 'concept_score',
      concept_name: selectedConceptInfo.name,
      namespace: selectedConceptInfo.namespace
    };

    $signalMutation.mutate([
      $datasetViewStore.namespace,
      $datasetViewStore.datasetName,
      {
        leaf_path: path,
        signal: conceptSignal
      }
    ]);
    close();
  }

  function close() {
    dispatch('close');
  }
</script>

<ComposedModal open on:submit={submit} on:close={close}>
  <ModalHeader title={'Compute concept'} />
  <ModalBody hasForm>
    <div class="flex flex-row">
      <div class="-ml-4 mr-4 w-96 grow-0">
        <ConceptList bind:selectedConceptInfo />
      </div>

      <div class="flex w-full flex-col gap-y-6 rounded border border-gray-300 bg-white p-4">
        {#if selectedConceptInfo && signalInfo}
          {#key selectedConceptInfo}
            <div class="flex flex-row items-center justify-between text-2xl font-semibold">
              <div>{selectedConceptInfo.name}</div>
              <button>
                <a href={conceptLink(selectedConceptInfo.namespace, selectedConceptInfo.name)}>
                  <ArrowUpRight />
                </a>
              </button>
            </div>
            {#if selectedConceptInfo.metadata.description}
              <div>
                <SvelteMarkdown source={selectedConceptInfo.metadata.description} />
              </div>
            {/if}

            <div>
              <FieldSelect
                filter={filterField}
                defaultPath={command.path}
                bind:path
                labelText="Field"
              />
            </div>

            <JsonSchemaForm
              schema={signalInfo.json_schema}
              bind:value={conceptPropertyValues}
              bind:validationErrors={errors}
              showDescription={false}
              hiddenProperties={['/signal_name', '/namespace', '/concept_name', '/draft']}
              customComponents={customComponents[signalInfo?.name]}
            />
          {/key}
        {:else}
          No signal selected
        {/if}
      </div>
    </div>
  </ModalBody>
  <ModalFooter
    primaryButtonText={'Compute'}
    secondaryButtonText="Cancel"
    primaryButtonDisabled={errors.length > 0 || path == null || selectedConceptInfo == null}
    on:click:button--secondary={close}
  />
</ComposedModal>
