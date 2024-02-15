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
  import {clusterMutation, queryFormatSelectors} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {serializePath, type Path} from '$lilac';
  import {
    ComposedModal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    Select,
    SelectItem,
    Toggle
  } from 'carbon-components-svelte';
  import FieldSelect from './commands/selectors/FieldSelect.svelte';
  $: options = $store;

  const clusterQuery = clusterMutation();
  const authInfo = queryAuthInfo();

  $: canComputeRemotely = $authInfo.data?.access.dataset.execute_remotely;

  $: formatSelectorsQuery =
    options != null ? queryFormatSelectors(options?.namespace, options?.datasetName) : null;

  let selectedFormatSelector: string | undefined = undefined;
  let formatSelectors: string[] | undefined = undefined;
  let outputColumn: string | undefined = undefined;
  $: outputColumnRequired = formatSelectors != null;
  $: {
    if (options?.output_path != null) {
      outputColumn = serializePath(options.output_path);
    }
  }
  $: {
    if (
      formatSelectorsQuery != null &&
      $formatSelectorsQuery != null &&
      $formatSelectorsQuery.data != null
    ) {
      selectedFormatSelector = $formatSelectorsQuery.data[0];
      formatSelectors = $formatSelectorsQuery.data;
    }
  }

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
        output_path: outputColumn,
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
      <div class="flex max-w-2xl flex-col gap-y-8">
        <div>
          <FieldSelect
            filter={f => f.dtype?.type === 'string'}
            defaultPath={options.input}
            bind:path={options.input}
            labelText="Field"
          />
        </div>
        {#if formatSelectors != null}
          <div>
            <div class="label text-s mb-2 font-medium text-gray-700">Selector</div>
            <Select hideLabel={true} bind:selected={selectedFormatSelector} required>
              {#each formatSelectors as formatSelector}
                <SelectItem value={formatSelector} text={formatSelector} />
              {/each}
            </Select>
          </div>
        {/if}
        <div>
          <div class="label text-s mb-2 font-medium text-gray-700">
            {outputColumnRequired ? '*' : ''} Output column
          </div>
          <input
            required={outputColumnRequired}
            class="h-full w-full rounded border border-neutral-300 p-2"
            placeholder="Choose a new column name to write clusters"
            bind:value={outputColumn}
          />
        </div>
        <div>
          <div class="label mb-2 font-medium text-gray-700">Use Garden</div>
          <div class="label text-sm text-gray-700">
            Accelerate computation by running remotely on <a
              href="https://lilacml.com/#garden"
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
            <div>
              <a href="https://forms.gle/Gz9cpeKJccNar5Lq8" target="_blank">
                Sign up for Lilac Garden
              </a>
              to enable this feature.
            </div>
          {/if}
        </div>
        <div>
          <div class="label text-s mb-2 font-medium text-gray-700">Overwrite</div>
          <Toggle labelA={'False'} labelB={'True'} bind:toggled={options.overwrite} hideLabel />
        </div>
      </div>
    </ModalBody>
    <ModalFooter
      primaryButtonText="Cluster"
      secondaryButtonText="Cancel"
      on:click:button--secondary={close}
      primaryButtonDisabled={outputColumnRequired && !outputColumn}
    />
  </ComposedModal>
{/if}
