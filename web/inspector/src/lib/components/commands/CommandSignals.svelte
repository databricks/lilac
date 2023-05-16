<script lang="ts">
  import {computeSignalColumnMutation} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {
    SIGNAL_INPUT_TYPE_TO_VALID_DTYPES,
    type LilacSchemaField,
    type Signal,
    type SignalInfoWithTypedSchema
  } from '$lilac';
  import {ComposedModal, ModalBody, ModalFooter, ModalHeader} from 'carbon-components-svelte';
  import type {JSONSchema4Type} from 'json-schema';
  import type {JSONError} from 'json-schema-library';
  import {createEventDispatcher} from 'svelte';
  import JsonSchemaForm from '../JSONSchema/JSONSchemaForm.svelte';
  import type {ComputeSignalCommand, PreviewConceptCommand} from './Commands.svelte';
  import FieldSelect from './selectors/FieldSelect.svelte';
  import SignalList from './selectors/SignalList.svelte';

  export let command: ComputeSignalCommand | PreviewConceptCommand;
  /** The variant of the command */
  export let variant: 'compute' | 'preview';

  let path = command.path;
  let signalInfo: SignalInfoWithTypedSchema | undefined;
  let signalPropertyValues: Record<string, JSONSchema4Type> = {};
  let errors: JSONError[] = [];

  const datasetViewStore = getDatasetViewContext();
  const dispatch = createEventDispatcher();

  const computeSignalMutation = computeSignalColumnMutation();

  $: {
    if (signalInfo?.name) setSignalName(signalInfo.name);
  }

  $: signal = signalPropertyValues as Signal;

  $: filterField = (field: LilacSchemaField) => {
    if (!field.dtype) return false;
    if (!signalInfo?.input_type) {
      return true;
    }
    const validDtypes = SIGNAL_INPUT_TYPE_TO_VALID_DTYPES[signalInfo.input_type];
    return validDtypes.includes(field.dtype);
  };

  function setSignalName(name: string) {
    signalPropertyValues.signal_name = name;
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
        datasetViewStore.addUdfColumn({
          path,
          signal_udf: signal
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
        <SignalList defaultSignal={command.signalName} bind:signal={signalInfo} />
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

            <JsonSchemaForm
              schema={signalInfo.json_schema}
              bind:value={signalPropertyValues}
              bind:validationErrors={errors}
              showDescription={false}
              hiddenProperties={['/signal_name']}
            />
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
    primaryButtonDisabled={errors.length > 0 || !path}
    on:click:button--secondary={close}
  />
</ComposedModal>
