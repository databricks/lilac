<script lang="ts">
  import {useComputeSignalColumnMutation} from '$lib/store/apiDataset';
  import {isSignalField} from '$lilac/lilac';
  import {ComposedModal, ModalBody, ModalFooter, ModalHeader} from 'carbon-components-svelte';
  import {createEventDispatcher} from 'svelte';
  import type {ComputeSignalCommand} from './Commands.svelte';
  import FieldSelect from './selectors/FieldSelect.svelte';
  import SignalSelect from './selectors/SignalSelect.svelte';

  export let command: ComputeSignalCommand;

  let path = command.path;
  let signalName = command.signalName;

  const dispatch = createEventDispatcher();

  $: computeSignalMutation = useComputeSignalColumnMutation(
    command.namespace,
    command.datasetName,
    {
      leaf_path: path || [],
      signal: {signal_name: signalName}
    }
  );

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
    <div class="flex flex-col gap-y-8">
      <FieldSelect
        filter={field => !isSignalField(field)}
        defaultPath={command.path}
        bind:path
        labelText="Field"
        helperText="Select field to calculate signal on"
      />
      <SignalSelect bind:signalName />
    </div>
  </ModalBody>
  <ModalFooter
    primaryButtonText="Compute"
    secondaryButtonText="Cancel"
    primaryButtonDisabled={!signalName || !path}
    on:click:button--secondary={close}
  />
</ComposedModal>
