<script lang="ts">
  import {goto} from '$app/navigation';
  import JsonSchemaForm from '$lib/components/JSONSchema/JSONSchemaForm.svelte';
  import DatasetNameInput from '$lib/components/datasets/huggingface/DatasetNameInput.svelte';
  import SplitsInput from '$lib/components/datasets/huggingface/SplitsInput.svelte';
  import {loadDatasetMutation, querySources, querySourcesSchema} from '$lib/queries/datasetQueries';
  import {watchTask} from '$lib/stores/taskMonitoringStore';
  import {datasetLink} from '$lib/utils';
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

  const sources = querySources();
  const loadDataset = loadDatasetMutation();

  let namespace = 'local';
  let name = '';
  let selectedSource = 'huggingface';
  let errors: JSONError[] = [];

  $: sourcesSchema = querySourcesSchema(selectedSource);

  // Dictionary of source schema property values
  let sourceSchemaValues: Record<string, JSONSchema4Type> = {};

  $: sourceSchemaValues['source_name'] = `${namespace}/${name}`;

  function submit() {
    if (errors.length) return;
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
          watchTask(resp.task_id, () => {
            goto(datasetLink(namespace, name));
          });
        }
      }
    );
  }
</script>

<div class="h-full w-full overflow-y-auto py-8">
  <div class="mx-auto flex max-w-xl flex-col">
    <h2>Add dataset</h2>
    <Form class="pt-8">
      <FormGroup legendText="Name">
        <!-- Input field for namespace and name -->
        <div class="flex flex-row content-start">
          <TextInput labelText="namespace" bind:value={namespace} invalid={!namespace} />
          <span class="mx-4 mt-6 text-lg">/</span>
          <TextInput labelText="name" bind:value={name} invalid={!name} />
        </div>
      </FormGroup>
      <FormGroup legendText="Data Loader">
        <!-- Radio button for selecting data loader -->
        {#if $sources.isSuccess}
          <div>
            <RadioButtonGroup bind:selected={selectedSource}>
              {#each $sources.data.sources as source}
                <RadioButton labelText={source} value={source} />
              {/each}
            </RadioButtonGroup>
          </div>
        {:else if $sources.isError}
          <InlineNotification
            kind="error"
            title="Error"
            subtitle={$sources.error.message}
            hideCloseButton
          />
        {:else if $sources.isLoading}
          <RadioButtonSkeleton />
        {/if}

        {#if $sourcesSchema.isSuccess}
          {@const schema = $sourcesSchema.data}
          {#key selectedSource}
            <!-- Data Loader Fields -->
            <JsonSchemaForm
              {schema}
              hiddenProperties={['/source_name']}
              bind:value={sourceSchemaValues}
              bind:validationErrors={errors}
              customComponents={selectedSource === 'huggingface'
                ? {
                    '/dataset_name': DatasetNameInput,
                    '/split': SplitsInput
                  }
                : {}}
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
      <Button on:click={submit} disabled={errors?.length > 0 || !name || !namespace}>Add</Button>
    </Form>
  </div>
</div>

<style lang="postcss">
  :global(.bx--form-item) {
    @apply mb-6;
  }

  :global(.bx--fieldset) {
    @apply rounded border border-gray-300 p-4;
  }

  :global(legend.bx--label) {
    @apply px-2 text-lg;
  }
</style>
