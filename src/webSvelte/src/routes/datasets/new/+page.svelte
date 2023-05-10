<script lang="ts">
  import {goto} from '$app/navigation';
  import JsonSchemaForm from '$lib/components/JSONSchema/JSONSchemaForm.svelte';
  import {
    useGetSourceSchemaQuery,
    useGetSourcesQuery,
    useLoadDatasetMutation
  } from '$lib/store/apiDataset';
  import {watchTask} from '$lib/store/taskMonitoring';
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

  const sources = useGetSourcesQuery();
  const loadDatasetMutation = useLoadDatasetMutation();

  let namespace = 'local';
  let name = '';
  let selectedSource = 'huggingface';
  let errors: JSONError[] = [];

  $: sourcesSchema = useGetSourceSchemaQuery(selectedSource);

  // Dictionary of source schema property values
  let sourceSchemaValues: Record<string, JSONSchema4Type> = {};

  $: sourceSchemaValues['source_name'] = `${namespace}/${name}`;

  function submit() {
    if (errors.length) return;
    $loadDatasetMutation.mutate(
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
            goto(`/datasets/${namespace}/${name}`);
          });
        }
      }
    );
  }
</script>

<div class="mx-auto flex max-w-lg flex-col">
  <h2>Add dataset</h2>
  <Form>
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

<style lang="postcss">
  :global(.bx--form-item) {
    @apply mb-6;
  }
</style>
