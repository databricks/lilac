<script lang="ts">
  import {editConceptMutation} from '$lib/queries/conceptQueries';
  import type {Concept} from '$lilac';
  import ThumbsDownFilled from 'carbon-icons-svelte/lib/ThumbsDownFilled.svelte';
  import ThumbsUpFilled from 'carbon-icons-svelte/lib/ThumbsUpFilled.svelte';
  import ConceptExampleList from './ConceptExampleList.svelte';

  export let concept: Concept;
  const conceptMutation = editConceptMutation();

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

<div class="flex h-full gap-x-4">
  <div class="flex w-1/2 flex-col gap-y-4">
    <span class="flex items-center gap-x-2 text-lg"
      ><ThumbsUpFilled /> Positive Examples ({positiveExamples.length} examples)</span
    >
    <ConceptExampleList
      data={positiveExamples}
      on:remove={ev => remove(ev.detail)}
      on:add={ev => add(ev.detail, true)}
    />
  </div>
  <div class="flex w-1/2 flex-col gap-y-4">
    <span class="flex items-center gap-x-2 text-lg"
      ><ThumbsDownFilled />Negative Examples ({negativeExamples.length} examples)</span
    >
    <ConceptExampleList
      data={negativeExamples}
      on:remove={ev => remove(ev.detail)}
      on:add={ev => add(ev.detail, false)}
    />
  </div>
</div>
