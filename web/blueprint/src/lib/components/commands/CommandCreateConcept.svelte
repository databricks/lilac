<script lang="ts">
  import {createConceptMutation, editConceptMutation} from '$lib/queries/conceptQueries';
  import {queryDatasetSchema, queryDatasets} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {
    ConceptsService,
    DatasetsService,
    ROWID,
    childFields,
    deserializePath,
    isSignalField,
    serializePath
  } from '$lilac';
  import {
    Button,
    ComposedModal,
    InlineLoading,
    InlineNotification,
    ModalBody,
    ModalFooter,
    ModalHeader,
    Select,
    SelectItem,
    SelectSkeleton,
    TextInput
  } from 'carbon-components-svelte';
  import {createEventDispatcher} from 'svelte';
  import type {CreateConceptCommand} from './Commands.svelte';
  import ExamplesList from './ExamplesList.svelte';

  export let command: CreateConceptCommand;

  const authInfo = queryAuthInfo();
  $: authEnabled = $authInfo.data?.auth_enabled;
  $: userId = $authInfo.data?.user?.id;

  $: defaultNamespace = command.namespace || (authEnabled ? userId : null);

  let namespace = defaultNamespace || 'local';
  $: {
    if (userId != null) {
      namespace = userId;
    }
  }
  $: dataset = command.dataset;
  $: datasetId = dataset ? `${dataset.namespace}/${dataset.name}` : '';
  $: path = command.path;
  $: pathId = path ? serializePath(path) : undefined;

  let name = command.conceptName || '';
  let conceptDescription: string | undefined;
  let generatingPositives = false;
  let generatingNegatives = false;

  const conceptCreate = createConceptMutation();
  const conceptEdit = editConceptMutation();

  const dispatch = createEventDispatcher();

  const datasets = queryDatasets();
  $: schemaQuery = dataset && queryDatasetSchema(dataset.namespace, dataset.name);
  $: schema = schemaQuery && $schemaQuery?.data;

  $: stringFields = schema
    ? childFields(schema).filter(f => f.dtype === 'string' && !isSignalField(f))
    : [];
  $: fields = stringFields.sort((a, b) => {
    const aIsIndexed = childFields(a).some(
      f => f.signal != null && childFields(f).some(f => f.dtype === 'embedding')
    );
    const bIsIndexed = childFields(b).some(
      f => f.signal != null && childFields(f).some(f => f.dtype === 'embedding')
    );
    if (aIsIndexed && !bIsIndexed) return -1;
    if (!aIsIndexed && bIsIndexed) return 1;
    return 0;
  });

  $: {
    // Auto-select the first dataset.
    if ($datasets.data && $datasets.data.length > 0 && dataset === undefined) {
      dataset = {namespace: $datasets.data[0].namespace, name: $datasets.data[0].dataset_name};
    }
  }

  $: {
    // Auto-select the first path.
    if (fields && fields.length > 0 && path === undefined) {
      path = fields[0].path;
    }
  }

  function datasetSelected(e: Event) {
    const val = (e.target as HTMLInputElement).value;
    if (val === '') {
      dataset = undefined;
    } else {
      const [namespace, name] = val.split('/');
      dataset = {namespace, name};
    }
    path = undefined;
  }

  function fieldSelected(e: Event) {
    const val = (e.target as HTMLInputElement).value;
    path = deserializePath(val);
  }

  let positiveExamples: string[] = [''];
  let negativeExamples: string[] = [''];

  function submit() {
    $conceptCreate.mutate(
      [{namespace, name, type: 'text', metadata: {description: conceptDescription}}],
      {
        onSuccess: () => {
          $conceptEdit.mutate(
            [
              namespace,
              name,
              {
                insert: [
                  ...positiveExamples.filter(text => text != '').map(text => ({text, label: true})),
                  ...negativeExamples.filter(text => text != '').map(text => ({text, label: false}))
                ]
              }
            ],
            {
              onSuccess: () => {
                dispatch('create', {namespace, name});
                close();
              }
            }
          );
        }
      }
    );
  }

  async function generatePositives() {
    if (!conceptDescription) return;
    generatingPositives = true;
    const examples = await ConceptsService.generateExamples(conceptDescription);
    generatingPositives = false;
    if (positiveExamples.at(-1) === '') {
      positiveExamples.pop();
    }
    positiveExamples.push(...examples);
    positiveExamples = positiveExamples;
  }

  async function generateNegatives() {
    if (!dataset || !path) return;
    generatingNegatives = true;
    const result = await DatasetsService.selectRows(dataset.namespace, dataset.name, {
      columns: [path],
      limit: 10,
      sort_by: [ROWID] // Sort by rowid to get random rows.
    });
    generatingNegatives = false;
    if (negativeExamples.at(-1) === '') {
      negativeExamples.pop();
    }
    const examples = result.rows.map(r => r[pathId!]);
    negativeExamples.push(...examples);
    negativeExamples = negativeExamples;
  }

  function close() {
    dispatch('close');
  }
</script>

<ComposedModal open on:submit={submit} on:close={close} size="lg">
  <ModalHeader title="New Concept" />
  <ModalBody hasForm>
    <div class="flex flex-col gap-y-8">
      <section>
        <div class="header-step">Step 1. Concept details</div>
        <div class="flex flex-row gap-x-12">
          {#if authEnabled}
            <!--
          When authentication is enabled, the namespace is the user id so we don't show it
          to the user.
        -->
            <TextInput labelText="namespace" disabled />
          {:else}
            <TextInput
              labelText="namespace"
              value={namespace}
              on:change={e => (namespace = (e.detail || '').toString())}
            />
          {/if}
          <TextInput labelText="name" bind:value={name} required />
        </div>
        {#if authEnabled}
          <div class="mb-8 text-xs text-neutral-700">
            This concept will be created under your namespace, so only will be visible to you.
          </div>
        {/if}
      </section>
      <section>
        <div class="header-step">Step 2. Add positive examples</div>
        <div class="my-4 flex gap-x-2">
          <TextInput
            labelText="Concept description"
            helperText={authEnabled
              ? 'Authentication is enabled, so LLM generation of examples is disabled. ' +
                'Please fork this and disable authentication to use generated examples.'
              : 'This will be used by an LLM to generate example sentences.'}
            placeholder="Enter the concept description..."
            bind:value={conceptDescription}
          />
          <div class="generate-button pt-6">
            <Button
              on:click={generatePositives}
              disabled={!conceptDescription || generatingPositives || authEnabled}
            >
              Generate
              <span class="ml-2" class:invisible={!generatingPositives}><InlineLoading /></span>
            </Button>
          </div>
        </div>
        <ExamplesList bind:examples={positiveExamples} />
      </section>
      <section>
        <div class="header-step">Step 3. Add negative examples</div>
        <div class="my-4 flex items-end gap-x-2">
          {#if $datasets.isLoading}
            <SelectSkeleton />
          {:else if $datasets.isError}
            <InlineNotification
              kind="error"
              title="Error"
              subtitle={$datasets.error.message}
              hideCloseButton
            />
          {:else if $datasets.data.length > 0}
            <Select labelText="Dataset" on:change={datasetSelected} selected={datasetId}>
              {#each $datasets.data as dataset}
                <SelectItem value={`${dataset.namespace}/${dataset.dataset_name}`} />
              {/each}
            </Select>
          {/if}

          {#if $schemaQuery?.isLoading}
            <SelectSkeleton />
          {:else if $schemaQuery?.isError}
            <InlineNotification
              kind="error"
              title="Error"
              subtitle={$schemaQuery.error.message}
              hideCloseButton
            />
          {:else if fields.length > 0}
            <Select labelText="Field" on:change={fieldSelected} selected={pathId}>
              {#each fields as field}
                <SelectItem value={serializePath(field.path)} />
              {/each}
            </Select>
          {/if}
          <div class="generate-button">
            <Button on:click={generateNegatives} disabled={!dataset || !path}>
              Generate
              <span class="ml-2" class:invisible={!generatingNegatives}><InlineLoading /></span>
            </Button>
          </div>
        </div>
        <ExamplesList bind:examples={negativeExamples} />
      </section>
    </div>
  </ModalBody>
  <ModalFooter
    primaryButtonText="Create"
    secondaryButtonText="Cancel"
    primaryButtonDisabled={namespace.length == 0 || name.length == 0}
    on:click:button--secondary={close}
  />
</ComposedModal>

<style lang="postcss">
  .header-step {
    @apply mb-2 text-base;
  }
  :global(.generate-button .bx--btn) {
    @apply h-10 min-h-0;
  }
</style>
