<script lang="ts">
  import {useComputeSignalColumnMutation} from '$lib/store/apiDataset';
  import {getDatasetViewContext} from '$lib/store/datasetViewStore';
  import {
    ENRICHMENT_TYPE_TO_VALID_DTYPES,
    type LilacSchemaField,
    type Signal,
    type SignalInfoWithTypedSchema
  } from '$lilac';
  import {
    ComposedModal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    TextInput
  } from 'carbon-components-svelte';
  import type {JSONSchema7} from 'json-schema';
  import {createEventDispatcher} from 'svelte';
  import type {ComputeSignalCommand, PreviewConceptCommand} from './Commands.svelte';
  import FieldSelect from './selectors/FieldSelect.svelte';
  import SignalSelect from './selectors/SignalSelect.svelte';

  export let command: ComputeSignalCommand | PreviewConceptCommand;
  /** The variant of the command */
  export let variant: 'compute' | 'preview';

  let path = command.path;
  let signalInfo: SignalInfoWithTypedSchema | undefined;
  let signalPropertyValues: Record<string, string> = {};

  const datasetViewStore = getDatasetViewContext();
  const dispatch = createEventDispatcher();

  const computeSignalMutation = useComputeSignalColumnMutation();

  // Reset the signal property values when signal changes
  $: {
    if (signalInfo) setSignalPropertyDefaults(signalInfo);
  }

  $: signal = {
    signal_name: signalInfo?.name,
    ...signalPropertyValues
  } as Signal;

  $: filterField = (field: LilacSchemaField) => {
    if (!field.dtype) return false;
    if (!signalInfo?.enrichment_type) {
      return true;
    }
    const validDtypes = ENRICHMENT_TYPE_TO_VALID_DTYPES[signalInfo.enrichment_type];
    return validDtypes.includes(field.dtype);
  };

  // Find the propties that should be displayed in ui
  $: visibleProperties = signalInfo ? filterVisibleProperties(signalInfo) : [];

  // Validate the signal property values when they change
  $: errors = validateSignalPropertyValues(signalPropertyValues);

  // Reset the signal property values with signal property defaults
  function setSignalPropertyDefaults(signal: SignalInfoWithTypedSchema) {
    signalPropertyValues = {};
    Object.entries(signal.json_schema.properties || {}).forEach(([key, property]) => {
      if (typeof property == 'object' && property.default) {
        signalPropertyValues[key] = property.default.toString();
      }
    });
    signalPropertyValues = signalPropertyValues;
  }

  function validateSignalPropertyValues(values: Record<string, string>) {
    const errors: Record<string, string> = {};
    Object.keys(signalInfo?.json_schema.properties || {}).forEach(key => {
      if (signalInfo?.json_schema.required?.includes(key) && !values[key]) {
        errors[key] = 'Required';
      }
    });
    return errors;
  }

  function filterVisibleProperties(signal: SignalInfoWithTypedSchema): [string, JSONSchema7][] {
    return Object.entries(signal.json_schema.properties || {})
      .filter(([_, property]) => {
        return typeof property == 'object';
      })
      .filter(([key]) => {
        return key != 'signal_name';
      }) as [string, JSONSchema7][];
  }

  function submit() {
    if (variant == 'compute') {
      $computeSignalMutation.mutate([
        command.namespace,
        command.datasetName,
        {
          leaf_path: path || [],
          signal
        }
      ]);
    } else if (variant == 'preview') {
      if (path) {
        datasetViewStore.addExtraColumn({
          feature: path,
          transform: {signal}
        });
      }
    }
    close();
  }

  function close() {
    dispatch('close');
  }
</script>

<ComposedModal open on:submit={submit} on:close={close}>
  <ModalHeader label="Signals" title={variant == 'compute' ? 'Compute Signal' : 'Preview Signal'} />
  <ModalBody hasForm>
    <div class="flex flex-row">
      <div class="-ml-4 mr-4 w-80 grow-0">
        <SignalSelect defaultSignal={command.signalName} bind:signal={signalInfo} />
      </div>

      <div class="flex w-full flex-col gap-y-6">
        {#if signalInfo}
          {#key signalInfo}
            <div>
              {signalInfo.json_schema.description}
            </div>

            <FieldSelect
              filter={filterField}
              defaultPath={command.path}
              bind:path
              labelText="Field"
            />

            {#each visibleProperties as [key, property]}
              <TextInput
                labelText={property.title}
                bind:value={signalPropertyValues[key]}
                invalid={!!errors[key]}
                invalidText={errors[key]}
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
    primaryButtonText={variant == 'compute' ? 'Compute' : 'Preview'}
    secondaryButtonText="Cancel"
    primaryButtonDisabled={Object.values(errors).length > 0}
    on:click:button--secondary={close}
  />
</ComposedModal>
