<script lang="ts">
  import {conceptModelMutation} from '$lib/queries/conceptQueries';
  import type {Concept, ConceptModelInfo} from '$lilac';
  import {Button, InlineLoading} from 'carbon-components-svelte';
  import {Chip} from 'carbon-icons-svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import ConceptHoverPill from './ConceptHoverPill.svelte';
  import {scoreToColor, scoreToText} from './colors';

  export let concept: Concept;
  export let embedding: string;

  export let model: ConceptModelInfo | undefined;
  export let isFetching: boolean;

  const modelMutation = conceptModelMutation();
</script>

<div
  class="flex w-36 flex-col items-center gap-y-2 rounded-md border border-b-0 border-gray-200 p-4 shadow-md"
  style="height: 103px"
>
  <div class="text-gray-500">{embedding}</div>
  {#if isFetching}
    <div class="flex flex-col items-center">
      <InlineLoading />
    </div>
  {:else if model?.metrics}
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
    {@const createModelIfNotExists = true}
    <Button
      icon={$modelMutation.isLoading ? InlineLoading : Chip}
      on:click={() =>
        $modelMutation.mutate([
          concept.namespace,
          concept.concept_name,
          embedding,
          createModelIfNotExists
        ])}
      class="w-28 text-3xl"
    >
      Compute
    </Button>
  {/if}
</div>
