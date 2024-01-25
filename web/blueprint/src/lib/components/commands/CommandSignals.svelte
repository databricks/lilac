<script context="module" lang="ts">
  const COMMAND_SIGNAL_CONTEXT = 'COMMAND_SIGNAL_CONTEXT';

  interface CommandSignalStore {
    path: Path | undefined;
    jsonSchema: JSONSchema7 | undefined;
  }

  export function getCommandSignalContext() {
    return getContext<Readable<CommandSignalStore>>(COMMAND_SIGNAL_CONTEXT);
  }

  export function createCommandSignalContext(path?: Path, jsonSchema?: JSONSchema7) {
    const store = writable<CommandSignalStore>({path, jsonSchema});
    setContext(COMMAND_SIGNAL_CONTEXT, store);
    return store;
  }
</script>

<script lang="ts">
  import {computeSignalMutation} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {
    SIGNAL_INPUT_TYPE_TO_VALID_DTYPES,
    type LilacField,
    type Path,
    type Signal,
    type SignalInfoWithTypedSchema
  } from '$lilac';
  import {
    ComposedModal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    Toggle
  } from 'carbon-components-svelte';
  import type {JSONSchema4Type, JSONSchema7} from 'json-schema';
  import type {JSONError} from 'json-schema-library';
  import {SvelteComponent, createEventDispatcher, getContext, setContext} from 'svelte';
  import SvelteMarkdown from 'svelte-markdown';
  import {writable, type Readable} from 'svelte/store';
  import JsonSchemaForm from '../JSONSchema/JSONSchemaForm.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import {
    Command,
    type ComputeEmbeddingCommand,
    type ComputeSignalCommand,
    type EditPreviewConceptCommand,
    type PreviewConceptCommand
  } from './Commands.svelte';
  import EmptyComponent from './customComponents/EmptyComponent.svelte';
  import SelectConcept from './customComponents/SelectConcept.svelte';
  import SelectEmbedding from './customComponents/SelectEmbedding.svelte';
  import EmbeddingList from './selectors/EmbeddingList.svelte';
  import FieldSelect from './selectors/FieldSelect.svelte';
  import SignalList from './selectors/SignalList.svelte';

  export let command:
    | ComputeSignalCommand
    | ComputeEmbeddingCommand
    | PreviewConceptCommand
    | EditPreviewConceptCommand;

  let path = command.path;
  let signalInfo: SignalInfoWithTypedSchema | undefined;
  let signalPropertyValues: Record<string, Record<string, JSONSchema4Type>> = {};
  let errors: JSONError[] = [];

  let overwrite = false;
  let useGarden = false;

  $: supportsGarden = signalInfo?.json_schema?.properties?.['supports_garden'];

  const HIDDEN_PROPERTIES = [
    // Hide the signal name as it's just used for type coersion.
    '/signal_name',
    '/supports_garden',
    // Hide the embedding input type from the compute embedding menu as we're always computing
    // document level embeddings.
    '/embed_input_type'
  ];

  // Set the signal values if we are editing a signal
  if (
    (command.command === Command.EditPreviewConcept ||
      command.command == Command.ComputeSignalCommand) &&
    command.signalName
  ) {
    signalPropertyValues = {[command.signalName]: {...command.value}};
  }

  // Store the field path and json schema in the context so custom components can access it
  const contextStore = createCommandSignalContext(path, signalInfo?.json_schema);
  $: $contextStore.path = path;
  $: $contextStore.jsonSchema = signalInfo?.json_schema;

  const datasetViewStore = getDatasetViewContext();
  const dispatch = createEventDispatcher();

  const signalMutation = computeSignalMutation();

  const customComponents: Record<string, Record<string, typeof SvelteComponent>> = {
    concept_score: {
      '/namespace': EmptyComponent,
      '/concept_name': SelectConcept,
      '/embedding': SelectEmbedding
    }
  };

  $: {
    if (signalInfo?.name) setSignalName(signalInfo.name);
  }

  $: signal = signalInfo?.name ? (signalPropertyValues[signalInfo.name] as Signal) : undefined;

  $: filterField = (field: LilacField) => {
    if (!field.dtype?.type) return false;
    if (!signalInfo?.input_type || signalInfo.input_type === 'any') {
      return true;
    }
    const validDtypes = SIGNAL_INPUT_TYPE_TO_VALID_DTYPES[signalInfo.input_type].map(
      dtype => dtype.type
    );
    return validDtypes.includes(field.dtype.type);
  };

  function setSignalName(name: string) {
    if (!(name in signalPropertyValues)) {
      signalPropertyValues[name] = {};
    }
    signalPropertyValues[name].signal_name = name;
  }

  function submit() {
    if (!signal) return;
    if (command.command === Command.ComputeSignal || command.command === Command.ComputeEmbedding) {
      $signalMutation.mutate([
        command.namespace,
        command.datasetName,
        {
          leaf_path: path || [],
          signal,
          overwrite,
          use_garden: useGarden
        }
      ]);
    } else if (command.command === Command.PreviewConcept) {
      if (path) {
        datasetViewStore.addUdfColumn({
          path: path,
          signal_udf: signal
        });
      }
    } else if (command.command === Command.EditPreviewConcept) {
      if (path) {
        datasetViewStore.editUdfColumn({
          path: path,
          signal_udf: signal
        });
      }
    }
    close();
  }

  function close() {
    dispatch('close');
  }

  $: title =
    command.command === Command.ComputeSignal
      ? 'Compute Signal'
      : command.command === Command.ComputeEmbedding
      ? 'Compute Embedding'
      : 'Preview Signal';

  const authInfo = queryAuthInfo();
  $: canComputeRemotely = $authInfo.data?.access.dataset.execute_remotely;
</script>

<ComposedModal open on:submit={submit} on:close={close}>
  <ModalHeader {title} />
  <ModalBody hasForm>
    <div class="flex flex-row">
      <div class="-ml-4 mr-4 w-96 grow-0">
        {#if command.command === Command.ComputeEmbedding}
          <EmbeddingList bind:embedding={signalInfo} />
        {:else}
          <SignalList defaultSignal={command.signalName} bind:signal={signalInfo} />
        {/if}
      </div>

      <div class="flex w-full flex-col gap-y-6 rounded border border-gray-300 bg-white p-4">
        {#if signalInfo}
          {#key signalInfo}
            <div class="markdown">
              <SvelteMarkdown source={signalInfo.json_schema.description} />
            </div>

            <FieldSelect
              filter={filterField}
              defaultPath={command.path}
              bind:path
              labelText="Field"
            />

            <JsonSchemaForm
              schema={signalInfo.json_schema}
              bind:value={signalPropertyValues[signalInfo?.name]}
              bind:validationErrors={errors}
              showDescription={false}
              hiddenProperties={HIDDEN_PROPERTIES}
              customComponents={customComponents[signalInfo?.name]}
            />
            <div class="mt-8">
              <div class="label text-s mb-2 font-medium text-gray-700">Overwrite</div>
              <Toggle labelA={'False'} labelB={'True'} bind:toggled={overwrite} hideLabel />
            </div>
            <div
              class="mt-8"
              use:hoverTooltip={{
                text: !supportsGarden ? 'Signal does not support Lilac Garden.' : ''
              }}
            >
              <div class="label mb-2 font-medium text-gray-700">Use Garden</div>
              <div class="label mb-2 text-sm text-gray-700">
                Accelerate computation by running remotely on <a
                  href="https://lilacml.com/garden"
                  target="_blank">Lilac Garden</a
                >
              </div>
              <Toggle
                disabled={!supportsGarden || !canComputeRemotely}
                labelA={'False'}
                labelB={'True'}
                bind:toggled={useGarden}
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
          {/key}
        {:else}
          No signal selected
        {/if}
      </div>
    </div>
  </ModalBody>
  <ModalFooter
    primaryButtonText={command.command === Command.ComputeSignal ||
    command.command === Command.ComputeEmbedding
      ? 'Compute'
      : 'Preview'}
    secondaryButtonText="Cancel"
    primaryButtonDisabled={errors.length > 0 || !path}
    on:click:button--secondary={close}
  />
</ComposedModal>
