<script lang="ts">
  import {
    editConceptMutation,
    queryConceptColumnInfos,
    queryConceptModels
  } from '$lib/queries/conceptQueries';
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {datasetLink} from '$lib/utils';
  import {
    formatValue,
    serializePath,
    type Concept,
    type ConceptModelInfo,
    type OverallScore
  } from '$lilac';
  import {InlineNotification, SkeletonText} from 'carbon-components-svelte';
  import {
    SkillLevel,
    SkillLevelAdvanced,
    SkillLevelBasic,
    SkillLevelIntermediate,
    ThumbsDown,
    type CarbonIcon
  } from 'carbon-icons-svelte';
  import ThumbsDownFilled from 'carbon-icons-svelte/lib/ThumbsDownFilled.svelte';
  import ThumbsUpFilled from 'carbon-icons-svelte/lib/ThumbsUpFilled.svelte';
  import ConceptExampleList from './ConceptExampleList.svelte';

  export let concept: Concept;
  const conceptMutation = editConceptMutation();
  const embeddings = queryEmbeddings();
  $: conceptModels = queryConceptModels(concept.namespace, concept.concept_name);
  let embeddingToModel: Record<string, ConceptModelInfo> = {};

  $: {
    if ($conceptModels.data) {
      embeddingToModel = {};
      for (const model of $conceptModels.data) {
        embeddingToModel[model.embedding_name] = model;
      }
    }
  }
  const scoreToColor: Record<OverallScore, string> = {
    not_good: 'text-red-600',
    ok: 'text-yellow-600',
    good: 'text-green-600',
    very_good: 'text-blue-600',
    great: 'text-purple-600'
  };

  const scoreToIcon: Record<OverallScore, typeof CarbonIcon> = {
    not_good: ThumbsDown,
    ok: SkillLevel,
    good: SkillLevelBasic,
    very_good: SkillLevelIntermediate,
    great: SkillLevelAdvanced
  };

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
</script>

<div class="flex h-full flex-col gap-y-8">
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
  {#if $embeddings.data}
    <div class="flex flex-col gap-y-2">
      <div class="text-lg font-semibold">Metrics</div>
      <div class="model-metrics flex gap-x-4">
        {#each $embeddings.data as embedding}
          {@const model = embeddingToModel[embedding.name]}
          <div
            class="flex flex-col items-center gap-y-2 rounded-md border border-gray-200 px-2 py-4"
          >
            <div class="text-gray-500">{embedding.name}</div>
            {#if model && model.metrics}
              <div class="text-4xl font-light {scoreToColor[model.metrics.overall]}">
                {formatValue(model.metrics.f1)}
              </div>
              <div>
                <svelte:component this={scoreToIcon[model.metrics.overall]} />
              </div>
            {:else}
              <button class="text-3xl">Compute</button>
            {/if}
          </div>
        {/each}
      </div>
    </div>
  {/if}
  <div class="flex w-full gap-x-4">
    <div class="flex w-1/2 flex-col gap-y-4">
      <span class="flex items-center gap-x-2 text-lg"
        ><ThumbsUpFilled /> Positive ({positiveExamples.length} examples)</span
      >
      <ConceptExampleList
        data={positiveExamples}
        on:remove={ev => remove(ev.detail)}
        on:add={ev => add(ev.detail, true)}
      />
    </div>
    <div class="flex w-1/2 flex-col gap-y-4">
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
