<script lang="ts">
  import {
    conceptModelMutation,
    editConceptMutation,
    queryConceptColumnInfos,
    queryConceptModels,
    queryConceptScore
  } from '$lib/queries/conceptQueries';
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {datasetLink} from '$lib/utils';
  import {serializePath, type Concept, type ConceptModelInfo} from '$lilac';
  import {
    Button,
    InlineLoading,
    InlineNotification,
    Select,
    SelectItem,
    SkeletonText,
    TextArea
  } from 'carbon-components-svelte';
  import {Chip} from 'carbon-icons-svelte';
  import ThumbsDownFilled from 'carbon-icons-svelte/lib/ThumbsDownFilled.svelte';
  import ThumbsUpFilled from 'carbon-icons-svelte/lib/ThumbsUpFilled.svelte';
  import Expandable from '../Expandable.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import ConceptExampleList from './ConceptExampleList.svelte';
  import ConceptHoverPill from './ConceptHoverPill.svelte';
  import ConceptViewFieldSelect from './ConceptViewFieldSelect.svelte';
  import {scoreToColor, scoreToText} from './colors';

  export let concept: Concept;

  const conceptScore = queryConceptScore();
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

  function remove(id: string) {
    if (!concept.namespace || !concept.concept_name) return;
    $conceptMutation.mutate([concept.namespace, concept.concept_name, {remove: [id]}]);
  }

  function add(text: string, label: boolean) {
    if (!concept.namespace || !concept.concept_name) return;
    $conceptMutation.mutate([concept.namespace, concept.concept_name, {insert: [{text, label}]}]);
  }

  let previewText: string;
  let previewEmbedding: string;
  function computeConcept() {
    if (previewText == null) return;
    $conceptScore.mutate([
      concept.namespace,
      concept.concept_name,
      previewEmbedding,
      {examples: [{text: previewText}]}
    ]);
  }
  $: console.log('score data', $conceptScore.data);
</script>

<div class="flex h-full w-full flex-col gap-y-8">
  <div>
    <div class="text-2xl font-semibold">{concept.namespace} / {concept.concept_name}</div>
    {#if concept.description}
      <div class="text text-base text-gray-600">{concept.description}</div>
    {/if}
  </div>

  {#if $embeddings?.data != null}
    <div class="flex flex-row gap-x-8">
      <div class="w-1/2">
        <div class="mb-2 w-32">
          <Select labelText="Embedding" bind:selected={previewEmbedding}>
            {#each $embeddings?.data as emdField}
              <SelectItem value={emdField.name} />
            {/each}
          </Select>
        </div>
        <TextArea
          bind:value={previewText}
          cols={50}
          placeholder="Paste text to test the concept."
          rows={4}
          class="mb-2"
        />
        <div class="flex flex-row">
          <div>
            <Button size="small" on:click={() => computeConcept()}>Preview</Button>
          </div>
        </div>
      </div>
      <div class="w-1/2">spans here</div>
    </div>
  {/if}

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
    {@const numDatasets = $conceptColumnInfos.data.length}
    <Expandable>
      <div slot="above" class="text-md font-semibold">Used on {numDatasets} datasets</div>
      <div slot="below" class="flex flex-col gap-y-3">
        {#each $conceptColumnInfos.data as column}
          <div>
            field <code>{serializePath(column.path)}</code> of dataset
            <a href={datasetLink(column.namespace, column.name)}>
              {column.namespace}/{column.name}
            </a>
          </div>
        {/each}
      </div>
    </Expandable>
  {/if}
  <Expandable>
    <div slot="above" class="text-md font-semibold">Collect labels</div>
    <ConceptViewFieldSelect {concept} slot="below" />
  </Expandable>
  {#if $embeddings.data}
    <div class="flex flex-col gap-y-2">
      <div class="text-md font-semibold">Metrics</div>
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
