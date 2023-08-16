<script lang="ts">
  import {editConceptMutation} from '$lib/queries/conceptQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import type {Concept} from '$lilac';
  import {ViewOff} from 'carbon-icons-svelte';
  import ThumbsDownFilled from 'carbon-icons-svelte/lib/ThumbsDownFilled.svelte';
  import ThumbsUpFilled from 'carbon-icons-svelte/lib/ThumbsUpFilled.svelte';
  import Expandable from '../Expandable.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import ConceptExampleList from './ConceptExampleList.svelte';
  import ConceptMetrics from './ConceptMetrics.svelte';
  import ConceptPreview from './ConceptPreview.svelte';
  import ConceptLabeler from './labeler/ConceptLabeler.svelte';

  export let concept: Concept;

  const authInfo = queryAuthInfo();
  $: userId = $authInfo.data?.user?.id;

  const conceptMutation = editConceptMutation();
  const embeddings = queryEmbeddings();

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

<div class="flex h-full w-full flex-col gap-y-8 px-10">
  <div>
    <div class="flex flex-row items-center text-2xl font-semibold">
      {concept.concept_name}
      {#if userId == concept.namespace}
        <div
          use:hoverTooltip={{
            text: 'Your concepts are only visible to you when logged in with Google.'
          }}
        >
          <ViewOff class="ml-2" />
        </div>
      {/if}
    </div>
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
          <ConceptMetrics {concept} embedding={embedding.name} />
        {/each}
      </div>
    </Expandable>
  {/if}
  <Expandable>
    <div slot="above" class="text-md font-semibold">Collect labels</div>
    <ConceptLabeler slot="below" {concept} />
  </Expandable>
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
