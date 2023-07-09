<script lang="ts">
  import {
    conceptModelMutation,
    editConceptMutation,
    queryConceptColumnInfos,
    queryConceptModels
  } from '$lib/queries/conceptQueries';
  import {queryDatasets} from '$lib/queries/datasetQueries';
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {datasetLink} from '$lib/utils';
  import {serializePath, type Concept, type ConceptModelInfo, type LilacSchema} from '$lilac';
  import {
    Button,
    InlineLoading,
    InlineNotification,
    Select,
    SelectItem,
    SelectSkeleton,
    SkeletonText
  } from 'carbon-components-svelte';
  import {Chip} from 'carbon-icons-svelte';
  import ThumbsDownFilled from 'carbon-icons-svelte/lib/ThumbsDownFilled.svelte';
  import ThumbsUpFilled from 'carbon-icons-svelte/lib/ThumbsUpFilled.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import ConceptExampleList from './ConceptExampleList.svelte';
  import ConceptHoverPill from './ConceptHoverPill.svelte';
  import ConceptViewFieldSelect from './ConceptViewFieldSelect.svelte';
  import ConceptViewLabeler from './ConceptViewLabeler.svelte';
  import {scoreToColor, scoreToText} from './colors';

  export let concept: Concept;

  // For training a concept.
  const datasets = queryDatasets();
  export let dataset: {namespace: string; name: string} | undefined | null = undefined;
  export let path: string[] | undefined = undefined;
  export let schema: LilacSchema | undefined = undefined;
  export let embedding: string | undefined = undefined;

  $: datasetId = dataset ? `${dataset.namespace}/${dataset.name}` : '';

  $: {
    // Auto-select the first dataset.
    if ($datasets.data && $datasets.data.length > 0 && dataset === undefined) {
      dataset = {namespace: $datasets.data[0].namespace, name: $datasets.data[0].dataset_name};
    }
  }

  const conceptMutation = editConceptMutation();
  const embeddings = queryEmbeddings();
  $: conceptModels = queryConceptModels(concept.namespace, concept.concept_name);
  let embeddingToModel: Record<string, ConceptModelInfo> = {};

  const modelMutation = conceptModelMutation();

  $: {
    if ($conceptModels.data) {
      embeddingToModel = {};
      for (const model of $conceptModels.data) {
        embeddingToModel[model.embedding_name] = model;
      }
    }
  }

  $: conceptColumnInfos = queryConceptColumnInfos(concept.namespace, concept.concept_name);
  $: positiveExamples = Object.values(concept.data).filter(v => v.label == true);
  $: negativeExamples = Object.values(concept.data).filter(v => v.label == false);

  function datasetSelected(e: Event) {
    const val = (e.target as HTMLInputElement).value;
    if (val === '') {
      dataset = null;
    } else {
      const [namespace, name] = val.split('/');
      dataset = {namespace, name};
    }
  }

  function remove(id: string) {
    if (!concept.namespace || !concept.concept_name) return;
    $conceptMutation.mutate([concept.namespace, concept.concept_name, {remove: [id]}]);
  }

  function add(text: string, label: boolean) {
    if (!concept.namespace || !concept.concept_name) return;
    $conceptMutation.mutate([concept.namespace, concept.concept_name, {insert: [{text, label}]}]);
  }
</script>

<div class="flex h-full w-full flex-col gap-y-8">
  <div>
    <div class="text-2xl font-semibold">{concept.namespace} / {concept.concept_name}</div>
    {#if concept.description}
      <div class="text text-base text-gray-600">{concept.description}</div>
    {/if}
  </div>

  {#if $conceptColumnInfos.isLoading}
    <SkeletonText />
  {:else if $conceptColumnInfos.isError}
    <InlineNotification
      kind="error"
      title="Error"
      subtitle={$conceptColumnInfos.error.message}
      hideCloseButton
    />
  {:else if $conceptColumnInfos.data.length > 0}
    <div>
      <div class="text-lg font-semibold">Used on</div>
      <div class="flex flex-col gap-y-2">
        {#each $conceptColumnInfos.data as column}
          <div>
            field <code>{serializePath(column.path)}</code> of dataset
            <a href={datasetLink(column.namespace, column.name)}>
              {column.namespace}/{column.name}
            </a>
          </div>
        {/each}
      </div>
    </div>
  {/if}
  <div>
    <div class="mb-4 text-lg font-semibold">Collect labels</div>
    <div class="flex flex-col gap-y-4">
      <div class="flex flex-row gap-x-2">
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
            <SelectItem value="" text="none" />
            {#each $datasets.data as dataset}
              <SelectItem value={`${dataset.namespace}/${dataset.dataset_name}`} />
            {/each}
          </Select>
        {/if}
        {#if dataset != null}
          {#key dataset}
            <ConceptViewFieldSelect {dataset} bind:path bind:schema bind:embedding />
          {/key}
        {/if}
      </div>
      {#if dataset != null && path != null && schema != null && embedding != null}
        <div>
          <ConceptViewLabeler {concept} {dataset} fieldPath={path} {schema} {embedding} />
        </div>
      {/if}
    </div>
  </div>
  {#if $embeddings.data}
    <div class="flex flex-col gap-y-2">
      <div class="text-lg font-semibold">Metrics</div>
      <div class="model-metrics flex gap-x-4">
        {#each $embeddings.data as embedding}
          {@const model = embeddingToModel[embedding.name]}
          {@const scoreIsLoading =
            $modelMutation.isLoading &&
            $modelMutation.variables &&
            $modelMutation.variables[2] == embedding.name}
          <div
            class="flex w-36 flex-col items-center gap-y-2 rounded-md border border-gray-300 p-4"
          >
            <div class="text-gray-500">{embedding.name}</div>
            {#if $conceptModels.isLoading}
              <InlineLoading />
            {:else if model && model.metrics}
              <div
                class="flex cursor-default flex-col items-center gap-y-2"
                use:hoverTooltip={{
                  component: ConceptHoverPill,
                  props: {metrics: model.metrics}
                }}
              >
                <div
                  class="concept-score-pill text-2xl font-light {scoreToColor[
                    model.metrics.overall
                  ]}"
                >
                  {scoreToText[model.metrics.overall]}
                </div>
              </div>
            {:else}
              <Button
                icon={scoreIsLoading ? InlineLoading : Chip}
                on:click={() =>
                  $modelMutation.mutate([concept.namespace, concept.concept_name, embedding.name])}
                class="w-28 text-3xl"
              >
                Compute
              </Button>
            {/if}
          </div>
        {/each}
      </div>
    </div>
  {/if}
  <div class="flex gap-x-4">
    <div class="flex w-0 flex-grow flex-col gap-y-4">
      <span class="flex items-center gap-x-2 text-lg"
        ><ThumbsUpFilled /> Positive ({positiveExamples.length} examples)</span
      >
      <ConceptExampleList
        data={positiveExamples}
        on:remove={ev => remove(ev.detail)}
        on:add={ev => add(ev.detail, true)}
      />
    </div>
    <div class="flex w-0 flex-grow flex-col gap-y-4">
      <span class="flex items-center gap-x-2 text-lg"
        ><ThumbsDownFilled />Negative ({negativeExamples.length} examples)</span
      >
      <ConceptExampleList
        data={negativeExamples}
        on:remove={ev => remove(ev.detail)}
        on:add={ev => add(ev.detail, false)}
      />
    </div>
  </div>
</div>
