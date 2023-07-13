<script lang="ts">
  import {
    conceptModelMutation,
    editConceptMutation,
    queryConceptColumnInfos,
    queryConceptModels
  } from '$lib/queries/conceptQueries';
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {datasetLink} from '$lib/utils';
  import {serializePath, type Concept, type ConceptModelInfo} from '$lilac';
  import {Button, InlineLoading, InlineNotification, SkeletonText} from 'carbon-components-svelte';
  import {Chip} from 'carbon-icons-svelte';
  import ThumbsDownFilled from 'carbon-icons-svelte/lib/ThumbsDownFilled.svelte';
  import ThumbsUpFilled from 'carbon-icons-svelte/lib/ThumbsUpFilled.svelte';
  import Expandable from '../Expandable.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import ConceptExampleList from './ConceptExampleList.svelte';
  import ConceptHoverPill from './ConceptHoverPill.svelte';
  import ConceptPreview from './ConceptPreview.svelte';
  import {scoreToColor, scoreToText} from './colors';
  import Labeler from './labeler/Labeler.svelte';

  export let concept: Concept;

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

  $: randomPositive = positiveExamples[Math.floor(Math.random() * positiveExamples.length)];

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

  <Expandable expanded>
    <div slot="above" class="text-md font-semibold">Try it</div>
    <ConceptPreview example={randomPositive} {concept} slot="below" />
  </Expandable>

  {#if $embeddings.data}
    <Expandable expanded>
      <div slot="above" class="text-md font-semibold">Metrics</div>
      <div slot="below" class="model-metrics flex gap-x-4">
        {#each $embeddings.data as embedding}
          {@const model = embeddingToModel[embedding.name]}
          {@const scoreIsLoading =
            $modelMutation.isLoading &&
            $modelMutation.variables &&
            $modelMutation.variables[2] == embedding.name}
          <div
            class="flex w-36 flex-col items-center gap-y-2 rounded-md border border-b-0 border-gray-200 p-4 shadow-md"
          >
            <div class="text-gray-500">{embedding.name}</div>
            {#if $conceptModels.isLoading}
              <InlineLoading />
            {:else if model && model.metrics}
              <div
                class="concept-score-pill cursor-default text-2xl font-light {scoreToColor[
                  model.metrics.overall
                ]}"
                use:hoverTooltip={{
                  component: ConceptHoverPill,
                  props: {metrics: model.metrics}
                }}
              >
                {scoreToText[model.metrics.overall]}
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
    </Expandable>
  {/if}
  <Expandable>
    <div slot="above" class="text-md font-semibold">Collect labels</div>
    <Labeler slot="below" {concept} />
  </Expandable>
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
  <div class="flex gap-x-4">
    <div class="flex w-0 flex-grow flex-col gap-y-4">
      <span class="flex items-center gap-x-2 text-lg"
        ><ThumbsUpFilled /> In concept ({positiveExamples.length} examples)</span
      >
      <ConceptExampleList
        data={positiveExamples}
        on:remove={ev => remove(ev.detail)}
        on:add={ev => add(ev.detail, true)}
      />
    </div>
    <div class="flex w-0 flex-grow flex-col gap-y-4">
      <span class="flex items-center gap-x-2 text-lg"
        ><ThumbsDownFilled />Not in concept ({negativeExamples.length} examples)</span
      >
      <ConceptExampleList
        data={negativeExamples}
        on:remove={ev => remove(ev.detail)}
        on:add={ev => add(ev.detail, false)}
      />
    </div>
  </div>
</div>
