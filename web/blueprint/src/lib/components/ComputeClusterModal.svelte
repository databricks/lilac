<script context="module" lang="ts">
  import {writable} from 'svelte/store';

  export type ClusterOptions = {
    namespace: string;
    datasetName: string;
    input: Path;
    output_path?: Path;
    remote?: boolean;
  };

  export function openClusterModal(options: ClusterOptions) {
    store.set(options);
  }

  let store = writable<ClusterOptions | null>(null);
</script>

<script lang="ts">
  import type {Path} from '$lilac';
  import {
    ComposedModal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    Toggle
  } from 'carbon-components-svelte';
  import FieldSelect from './commands/selectors/FieldSelect.svelte';
  $: options = $store;

  function close() {
    store.set(null);
  }
  function submit() {
    if (!options) return;
    // $signalMutation.mutate([
    //   command.namespace,
    //   command.datasetName,
    //   {
    //     leaf_path: path || [],
    //     signal
    //   }
    // ]);
    close();
  }
</script>

{#if options}
  <ComposedModal open on:submit={submit} on:close={close}>
    <ModalHeader title="Cluster" />
    <ModalBody hasForm>
      <div class="max-w-2xl">
        <FieldSelect
          filter={f => f.dtype?.type === 'string'}
          defaultPath={options.input}
          bind:path={options.input}
          labelText="Field"
        />
      </div>
      <div>
        <Toggle labelA={'False'} labelB={'True'} labelText="Remote" bind:toggled={options.remote} />
      </div>
    </ModalBody>
    <ModalFooter
      primaryButtonText="Cluster"
      secondaryButtonText="Cancel"
      on:click:button--secondary={close}
    />
  </ComposedModal>
{/if}
