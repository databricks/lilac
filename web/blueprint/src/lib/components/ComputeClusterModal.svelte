<script context="module" lang="ts">
  import {writable} from 'svelte/store';

  export type ClusterOptions = {
    namespace: string;
    datasetName: string;
    input: Path;
    output_path?: Path;
    use_garden?: boolean;
    overwrite?: boolean;
  };

  export function openClusterModal(options: ClusterOptions) {
    store.set(options);
  }

  let store = writable<ClusterOptions | null>(null);
</script>

<script lang="ts">
  import {clusterMutation} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
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

  const clusterQuery = clusterMutation();
  const authInfo = queryAuthInfo();

  $: canComputeRemotely = $authInfo.data?.access.dataset.execute_remotely;

  function close() {
    store.set(null);
  }
  function submit() {
    if (!options) return;
    $clusterQuery.mutate([
      options.namespace,
      options.datasetName,
      {
        input: options.input,
        use_garden: options.use_garden,
        output_path: options.output_path,
        overwrite: options.overwrite
      }
    ]);
    close();
  }
</script>

{#if options}
  <ComposedModal open on:submit={submit} on:close={close}>
    <ModalHeader title="Compute clusters" />
    <ModalBody hasForm>
      <div class="max-w-2xl">
        <FieldSelect
          filter={f => f.dtype?.type === 'string'}
          defaultPath={options.input}
          bind:path={options.input}
          labelText="Field"
        />
      </div>
      <div class="mt-8">
        <div class="label mb-2 font-medium text-gray-700">Use Garden</div>
        <div class="label mb-2 text-sm text-gray-700">
          Accelerate computation by running remotely on <a
            href="https://lilacml.com/garden"
            target="_blank">Lilac Garden</a
          >
        </div>
        <Toggle
          disabled={!canComputeRemotely}
          labelA={'False'}
          labelB={'True'}
          bind:toggled={options.use_garden}
          hideLabel
        />
        {#if !canComputeRemotely}
          <div class="mt-2">
            <a href="https://forms.gle/Gz9cpeKJccNar5Lq8" target="_blank">
              Sign up for Lilac Garden
            </a>
            to enable this feature.
          </div>
        {/if}
      </div>
      <div class="mt-8">
        <div class="label text-s mb-2 font-medium text-gray-700">Overwrite</div>
        <Toggle labelA={'False'} labelB={'True'} bind:toggled={options.overwrite} hideLabel />
      </div>
    </ModalBody>
    <ModalFooter
      primaryButtonText="Cluster"
      secondaryButtonText="Cancel"
      on:click:button--secondary={close}
    />
  </ComposedModal>
{/if}
