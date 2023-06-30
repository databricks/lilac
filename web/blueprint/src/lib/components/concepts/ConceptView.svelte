<script lang="ts">
  import {editConceptMutation, queryConceptColumnInfos} from '$lib/queries/conceptQueries';
  import {datasetLink} from '$lib/utils';
  import {serializePath, type Concept} from '$lilac';
  import {InlineNotification, SkeletonText} from 'carbon-components-svelte';
  import ThumbsDownFilled from 'carbon-icons-svelte/lib/ThumbsDownFilled.svelte';
  import ThumbsUpFilled from 'carbon-icons-svelte/lib/ThumbsUpFilled.svelte';
  import ConceptExampleList from './ConceptExampleList.svelte';

  export let concept: Concept;
  const conceptMutation = editConceptMutation();

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
            <a href={datasetLink(column.namespace, column.name)}
              >{column.namespace}/{column.name}
            </a>
            on field <code>{serializePath(column.path)}</code>
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
