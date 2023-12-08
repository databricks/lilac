<script lang="ts">
  import {querySignalCompute, querySignalSchema} from '$lib/queries/signalQueries';
  import {getSpanValuePaths} from '$lib/view_utils';
  import {
    deserializeField,
    deserializeRow,
    pathIncludes,
    petals,
    type DataTypeCasted,
    type LilacField,
    type LilacValueNode,
    type Path,
    type SignalInfoWithTypedSchema
  } from '$lilac';
  import {Button, SkeletonText, Tab, TabContent, Tabs, TextArea} from 'carbon-components-svelte';
  import type {JSONSchema4Type} from 'json-schema';
  import type {JSONError} from 'json-schema-library';
  import {onMount, type SvelteComponent} from 'svelte';
  import SvelteMarkdown from 'svelte-markdown';
  import JsonSchemaForm from '../JSONSchema/JSONSchemaForm.svelte';
  import EmptyComponent from '../commands/customComponents/EmptyComponent.svelte';
  import SelectConcept from '../commands/customComponents/SelectConcept.svelte';
  import SelectEmbedding from '../commands/customComponents/SelectEmbedding.svelte';
  import ItemMetadata from '../datasetView/ItemMetadata.svelte';
  import StringSpanHighlight from '../datasetView/StringSpanHighlight.svelte';
  import type {SpanValueInfo} from '../datasetView/spanHighlight';

  export let signalInfo: SignalInfoWithTypedSchema;

  export let text: string | undefined = undefined;

  // User entered text.
  let textAreaText = text?.trim() || '';

  // Auto-compute the text passed in if it's defined.
  onMount(() => {
    if (text != null) {
      computeSignal();
    }
  });

  // Reset the text when the example changes.
  $: {
    if (text != null) {
      textAreaText = text.trim();
      previewText = undefined;
    }
  }

  function textChanged(e: Event) {
    textAreaText = (e.target as HTMLTextAreaElement).value;
    previewText = undefined;
  }

  // The text shown in the highlight preview.
  let previewText: string | undefined = undefined;
  let propertyValues: Record<string, JSONSchema4Type> = {};

  $: signal = {...propertyValues, signal_name: signalInfo.name};
  $: compute =
    previewText != null
      ? querySignalCompute({
          signal,
          inputs: [previewText]
        })
      : null;
  $: signalSchema = querySignalSchema({signal});
  function computeSignal() {
    previewText = textAreaText;
  }

  let previewResultItem: LilacValueNode | undefined = undefined;
  // For spans.
  let valuePaths: SpanValueInfo[];
  let spanPaths: Path[];
  // For regular metadata.
  let metadataFields: LilacField[];
  // For primitives.
  let primitiveValue: DataTypeCasted;
  $: {
    if ($compute?.data != null && $signalSchema.data?.fields != null) {
      primitiveValue = null;
      const item = $compute.data.items[0];
      const resultSchema = deserializeField($signalSchema.data.fields);
      previewResultItem = deserializeRow(item, resultSchema);

      const spanValuePaths = getSpanValuePaths(resultSchema);
      spanPaths = spanValuePaths.spanPaths;
      valuePaths = spanValuePaths.valuePaths;

      const children = petals(resultSchema);

      // Find the non-span fields to render as a table.
      metadataFields = children.filter(f => {
        // Remove any children that are the child of a span.
        return !spanPaths.some(p => {
          return pathIncludes(f.path, p);
        });
      });

      if (children.length === 0) {
        // For primitive values, just show the value directly.
        primitiveValue = item as unknown as DataTypeCasted;
      }
    }
  }
  let errors: JSONError[] = [];
  const customComponents: Record<string, Record<string, typeof SvelteComponent>> = {
    concept_score: {
      '/namespace': EmptyComponent,
      '/concept_name': SelectConcept,
      '/embedding': SelectEmbedding
    }
  };
  $: hasOptions =
    Object.keys(signalInfo?.json_schema?.properties || {}).filter(p => p != 'signal_name').length >
    0;
</script>

<div class="flex h-full w-full flex-col gap-y-8 px-10">
  <div>
    <div class="mb-4 flex flex-row items-center text-2xl font-semibold">
      {signalInfo.json_schema.title}
    </div>
    {#if signalInfo.json_schema.description}
      <div class="markdown text text-base text-gray-600">
        <SvelteMarkdown source={signalInfo.json_schema.description} />
      </div>
    {/if}
  </div>
  <div class="w-full">
    <div class="flex w-full flex-col gap-x-8">
      <div>
        <TextArea
          value={textAreaText}
          on:input={textChanged}
          cols={50}
          placeholder="Paste text to try the signal."
          rows={6}
          class="mb-2"
        />
        <div class="flex flex-row justify-between">
          <div class="pt-4">
            <Button on:click={() => computeSignal()}>Compute</Button>
          </div>
        </div>
      </div>
      <div class:border-t={previewText != null} class="mb-8 mt-4 border-gray-200 pt-4">
        {#if $compute?.isFetching}
          <SkeletonText />
        {:else if previewResultItem != null && previewText != null && $compute?.data != null}
          <Tabs>
            <Tab label="Preview" />
            <Tab label="JSON response" />
            <svelte:fragment slot="content">
              <TabContent>
                <div class="mt-2">
                  {#if valuePaths.length > 0}
                    <StringSpanHighlight
                      text={previewText}
                      row={previewResultItem}
                      {spanPaths}
                      {valuePaths}
                      embeddings={[]}
                    />
                  {/if}
                  {#if metadataFields.length > 0}
                    <div style:width="500px">
                      <ItemMetadata row={previewResultItem} highlightedFields={[]} />
                    </div>
                  {/if}
                  {#if primitiveValue != null}
                    <div class="flex flex-row items-center">
                      <div class="text text-base">
                        {primitiveValue}
                      </div>
                    </div>
                  {/if}
                </div>
              </TabContent>
              <TabContent>
                <TextArea
                  value={JSON.stringify($compute.data.items[0], null, 2)}
                  readonly
                  rows={10}
                  class="mb-2 font-mono"
                />
              </TabContent>
            </svelte:fragment>
          </Tabs>
        {/if}
      </div>
      {#if hasOptions}
        <div>
          <h4>Signal options</h4>

          <JsonSchemaForm
            schema={signalInfo.json_schema}
            bind:value={propertyValues}
            bind:validationErrors={errors}
            showDescription={false}
            hiddenProperties={['/signal_name']}
            customComponents={customComponents[signalInfo?.name]}
          />
        </div>
      {/if}
    </div>
  </div>
</div>

<style lang="postcss">
  :global(.bx--tab-content) {
    @apply p-0;
  }
</style>
