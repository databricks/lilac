<script lang="ts">
  import type {Concept} from '$lilac';
  import ConceptExampleList from './ConceptExampleList.svelte';

  export let concept: Concept;

  $: positiveExamples = Object.values(concept.data).filter(v => v.label == true);
  $: negativeExamples = Object.values(concept.data).filter(v => v.label == false);
</script>

<div class="flex h-full gap-x-4">
  <div class="flex w-1/2 flex-col gap-y-4">
    <span class="text-lg">Positive Examples ({positiveExamples.length} examples)</span>
    <ConceptExampleList data={positiveExamples} />
  </div>
  <div class="flex w-1/2 flex-col gap-y-4">
    <span class="text-lg">Negative Examples ({negativeExamples.length} examples)</span>
    <ConceptExampleList data={negativeExamples} />
  </div>
</div>
