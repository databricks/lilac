<script lang="ts">
  import {goto} from '$app/navigation';
  import JsonSchemaForm from '$lib/components/JSONSchema/JSONSchemaForm.svelte';
  import Page from '$lib/components/Page.svelte';
  import ConfigInput from '$lib/components/datasets/huggingface/ConfigInput.svelte';
  import HFNameInput from '$lib/components/datasets/huggingface/HFNameInput.svelte';
  import SplitsInput from '$lib/components/datasets/huggingface/SplitsInput.svelte';
  import LangsmithDatasetInput from '$lib/components/datasets/langsmith/DatasetInput.svelte';
  import TableInput from '$lib/components/datasets/sqlite/TableInput.svelte';
  import {loadDatasetMutation, querySources, querySourcesSchema} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {datasetIdentifier} from '$lib/utils';

  import {
    Button,
    Form,
    FormGroup,
    InlineNotification,
    RadioButton,
    RadioButtonGroup,
    RadioButtonSkeleton,
    SkeletonText,
    TextInput
  } from 'carbon-components-svelte';
  import type {JSONSchema4Type} from 'json-schema';
  import type {JSONError} from 'json-schema-library';
  import type {SvelteComponent} from 'svelte';

  const IGNORE_SOURCES = ['pandas', 'llama_index_docs', 'gmail'];

  const sourcesQuery = querySources();
  $: sources = $sourcesQuery.data?.sources.filter(s => !IGNORE_SOURCES.includes(s));
  const loadDataset = loadDatasetMutation();

  const authInfo = queryAuthInfo();
  $: canCreateDataset = $authInfo.data?.access.create_dataset;

  let namespace = 'local';
  let name = '';
  let selectedSource = 'parquet';
  let jsonValidationErrors: JSONError[] = [];

  let namespaceError: string | undefined = undefined;
  let nameError: string | undefined = undefined;

  const CUSTOM_COMPONENTS: Record<string, Record<string, typeof SvelteComponent>> = {
    huggingface: {
      '/dataset_name': HFNameInput,
      '/split': SplitsInput,
      '/config_name': ConfigInput
    },
    langsmith: {
      '/dataset_name': LangsmithDatasetInput
    },
    sqlite: {
      '/table': TableInput
    }
  };
  $: {
    if (namespace == null || namespace == '') {
      namespaceError = 'Enter a namespace';
    } else if (namespace.includes('/')) {
      namespaceError = 'Namespace cannot contain "/"';
    } else {
      namespaceError = undefined;
    }
  }
  $: {
    if (name == null || name == '') {
      nameError = 'Enter a name';
    } else if (name.includes('/')) {
      nameError = 'Name cannot contain "/"';
    } else {
      nameError = undefined;
    }
  }

  $: sourcesSchema = querySourcesSchema(selectedSource);

  // Dictionary of source schema property values
  let sourceSchemaValues: Record<string, JSONSchema4Type> = {};

  $: sourceSchemaValues['source_name'] = selectedSource;

  function submit() {
    if (jsonValidationErrors.length) return;
    $loadDataset.mutate(
      [
        selectedSource,
        {
          namespace,
          dataset_name: name,
          config: sourceSchemaValues
        }
      ],
      {
        onSuccess: resp => {
          goto(`/datasets/loading#${datasetIdentifier(namespace, name)}/${resp.task_id}`);
        }
      }
    );
  }
</script>

<Page>
  <div class="flex h-full w-full gap-y-4 overflow-y-scroll p-4">
    <div class="new-form mx-auto flex h-full max-w-xl flex-col">
      <h2>Add dataset</h2>
      {#if canCreateDataset}
        <Form class="py-8">
          <FormGroup legendText="Name">
            <!-- Input field for namespace and name -->
            <div class="flex flex-row content-start">
              <TextInput
                labelText="namespace"
                bind:value={namespace}
                invalid={namespaceError != null}
                invalidText={namespaceError}
              />
              <span class="mx-4 mt-6 text-lg">/</span>
              <TextInput
                labelText="name"
                bind:value={name}
                invalid={nameError != null}
                invalidText={nameError}
              />
            </div>
          </FormGroup>
          <FormGroup legendText="Data Loader">
            <!-- Radio button for selecting data loader -->
            {#if $sourcesQuery.isFetching}
              <RadioButtonSkeleton />
            {:else if sources != null}
              <div>
                <RadioButtonGroup bind:selected={selectedSource} class="source-radio-buttons">
                  {#each sources as source}
                    <RadioButton labelText={source} value={source} />
                  {/each}
                </RadioButtonGroup>
              </div>
            {:else if $sourcesQuery.isError}
              <InlineNotification
                kind="error"
                title="Error"
                subtitle={$sourcesQuery.error.message}
                hideCloseButton
              />
            {/if}

            {#if $sourcesSchema.isSuccess}
              {@const schema = $sourcesSchema.data}
              {#key selectedSource}
                <!-- Data Loader Fields -->
                <JsonSchemaForm
                  {schema}
                  hiddenProperties={['/source_name']}
                  bind:value={sourceSchemaValues}
                  bind:validationErrors={jsonValidationErrors}
                  customComponents={CUSTOM_COMPONENTS[selectedSource] || {}}
                />
              {/key}
            {:else if $sourcesSchema.isError}
              <InlineNotification
                kind="error"
                title="Error"
                hideCloseButton
                subtitle={$sourcesSchema.error.message}
              />
            {:else if $sourcesSchema.isLoading}
              <div class="mt-4">
                <h3 class="text-lg">Schema</h3>
                <SkeletonText />
              </div>
            {/if}
          </FormGroup>
          <Button
            on:click={submit}
            disabled={jsonValidationErrors?.length > 0 ||
              nameError != null ||
              namespaceError != null}>Add</Button
          >
        </Form>
      {:else}
        <div class="mt-4 flex flex-col border border-neutral-100 bg-red-100 p-2">
          <span class="mb-2">You do not have authorization to create a dataset.</span>
          <span>
            For HuggingFace spaces, you can duplicate this space and remove authentication. See <a
              href="https://lilacml.com/huggingface/huggingface_spaces.html"
              >Duplicating the HuggingFace demo</a
            >.
          </span>
        </div>
      {/if}
    </div>
  </div>
</Page>

<style lang="postcss">
  :global(.new-form .bx--form-item) {
    @apply mb-6;
  }

  :global(.bx--fieldset) {
    @apply rounded border border-gray-300 p-4;
  }

  :global(legend.bx--label) {
    @apply px-2 text-lg;
  }
  :global(.source-radio-buttons fieldset) {
    @apply flex-wrap gap-y-2;
  }
</style>
