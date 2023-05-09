<script lang="ts">
  import {useComputeSignalColumnMutation} from '$lib/store/apiDataset';
  import type {LilacSignalInfo} from '$lib/store/apiSignal';
  import {ENRICHMENT_TYPE_TO_VALID_DTYPES, type LilacSchemaField} from '$lilac';
  import {
    ComposedModal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    TextInput
  } from 'carbon-components-svelte';
  import {createEventDispatcher} from 'svelte';
  import type {ComputeSignalCommand} from './Commands.svelte';
  import FieldSelect from './selectors/FieldSelect.svelte';
  import SignalSelect from './selectors/SignalSelect.svelte';

  export let command: ComputeSignalCommand;

  let path = command.path;
  let signal: LilacSignalInfo | undefined;

  let signalPropertyValues: Record<string, any> = {};

  const dispatch = createEventDispatcher();

  // TODO, feed in the signal property values to the mutation
  $: computeSignalMutation = useComputeSignalColumnMutation(
    command.namespace,
    command.datasetName,
    {
      leaf_path: path || [],
      signal: {signal_name: signal?.name}
    }
  );

  $: filterField = (field: LilacSchemaField) => {
    if (!field.dtype) return false;
    if (!signal?.enrichment_type) {
      return true;
    }
    const validDtypes = ENRICHMENT_TYPE_TO_VALID_DTYPES[signal.enrichment_type];
    return validDtypes.includes(field.dtype);
  };

  $: signalProperties = Object.entries(signal?.json_schema.properties || {})
    .map(([key, property]) => ({
      ...property,
      key: key
    }))
    // Filter out signal_name property
    .filter(property => property.key != 'signal_name');

  // Reset the signal property values when signal changes
  $: {
    if (signal) setSignalPropertyDefaults(signal);
  }

  // Validate the signal property values when they change
  $: errors = validateSignalPropertyValues(signalPropertyValues);

  // Reset the signal property values with signal property defaults
  function setSignalPropertyDefaults(signal: LilacSignalInfo) {
    signalPropertyValues = {};
    Object.entries(signal.json_schema.properties || {}).forEach(([key, property]) => {
      if (property.default) {
        signalPropertyValues[key] = property.default;
      }
    });
  }

  function validateSignalPropertyValues(values: Record<string, any>) {
    const errors: Record<string, string> = {};
    Object.entries(signal?.json_schema.properties || {}).forEach(([key, property]) => {
      if (signal?.json_schema.required?.includes(key) && !values[key]) {
        errors[key] = 'Required';
      }
    });
    return errors;
  }

  function submit() {
    $computeSignalMutation.mutate();
    close();
  }

  function close() {
    dispatch('close');
  }
</script>

<ComposedModal open on:submit={submit} on:close={close}>
  <ModalHeader label="Signals" title="Compute Signal" />
  <ModalBody hasForm>
    <div class="flex flex-row">
      <div class="-ml-4 mr-4 w-80 grow-0">
        <SignalSelect defaultSignal={command.signalName} bind:signal />
      </div>

      <div class="flex w-full flex-col gap-y-6">
        {#if signal}
          {#key signal}
            <div>
              {signal.json_schema.description}
            </div>

            <FieldSelect
              filter={filterField}
              defaultPath={command.path}
              bind:path
              labelText="Field"
            />

            {#each signalProperties as property}
              <TextInput
                labelText={property.title}
                bind:value={signalPropertyValues[property.key]}
                invalid={!!errors[property.key]}
                invalidText={errors[property.key]}
              />
            {/each}
          {/key}
        {:else}
          No signal selected
        {/if}
      </div>
    </div>
  </ModalBody>
  <ModalFooter
    primaryButtonText="Compute"
    secondaryButtonText="Cancel"
    primaryButtonDisabled={Object.values(errors).length > 0}
    on:click:button--secondary={close}
  />
</ComposedModal>
