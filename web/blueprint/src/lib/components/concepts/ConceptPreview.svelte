<script lang="ts">
  import {queryConceptScore} from '$lib/queries/conceptQueries';
  import {queryEmbeddings, querySignalSchema} from '$lib/queries/signalQueries';
  import {getSettingsContext} from '$lib/stores/settingsStore';
  import {getSpanValuePaths} from '$lib/view_utils';
  import {
    deserializeField,
    deserializeRow,
    type Concept,
    type Example,
    type LilacValueNode,
    type Path
  } from '$lilac';
  import {Button, Select, SelectItem, SkeletonText, TextArea} from 'carbon-components-svelte';
  import {onMount} from 'svelte';
  import StringSpanHighlight from '../datasetView/StringSpanHighlight.svelte';
  import {colorFromScore} from '../datasetView/colors';
  import type {SpanValueInfo} from '../datasetView/spanHighlight';

  export let concept: Concept;
  export let example: Example;

  const embeddings = queryEmbeddings();
  const settings = getSettingsContext();

  // User entered text.
  let textAreaText = example.text?.trim();

  // Auto-compute the first positive example.
  onMount(() => {
    computeConceptScore();
  });

  // Reset the text when the example changes.
  $: {
    if (example.text) {
      textAreaText = example.text.trim();
      previewText = undefined;
    }
  }

  function textChanged(e: Event) {
    textAreaText = (e.target as HTMLTextAreaElement).value;
    previewText = undefined;
  }

  // The text shown in the highlight preview.
  let previewText: string | undefined = undefined;
  let previewEmbedding = $settings.embedding;
  $: signal = {
    signal_name: 'concept_score',
    concept_name: concept.concept_name,
    namespace: concept.namespace,
    embedding: previewEmbedding
  };
  $: signalSchema = signal.embedding ? querySignalSchema({signal}) : undefined;

  $: conceptScore =
    previewEmbedding != null && previewText != null
      ? queryConceptScore(concept.namespace, concept.concept_name, previewEmbedding, {
          examples: [{text: previewText}]
        })
      : null;
  function computeConceptScore() {
    previewText = textAreaText;
  }

  let previewResultItem: LilacValueNode | undefined = undefined;
  let spanValueInfos: SpanValueInfo[];
  let spanPaths: Path[];
  $: {
    if (
      $conceptScore?.data != null &&
      previewEmbedding != null &&
      $signalSchema?.data?.fields != null
    ) {
      const resultSchema = deserializeField($signalSchema.data.fields);
      // Add the signal to the result schema as it doesn't come back with the response.
      resultSchema.signal = signal;
      previewResultItem = deserializeRow($conceptScore.data[0], resultSchema);
      const spanValuePaths = getSpanValuePaths(resultSchema);
      spanPaths = spanValuePaths.spanPaths;
      spanValueInfos = spanValuePaths.spanValueInfos;
    }
  }
  let maxConceptScore: number;
  // Compute the max score and show it separately.
  $: if ($conceptScore?.data != null) {
    maxConceptScore = 0;
    for (const row of $conceptScore.data[0]) {
      const score = row['score'] as number;
      maxConceptScore = Math.max(score, maxConceptScore);
    }
  }
</script>

<div class="flex flex-col gap-x-8">
  <div>
    <TextArea
      value={textAreaText}
      on:input={textChanged}
      cols={50}
      placeholder="Paste text to try the concept."
      rows={6}
      class="mb-2"
    />
    <div class="flex flex-row justify-between">
      <div class="pt-4">
        <Button on:click={() => computeConceptScore()}>Compute</Button>
      </div>
      <div class="mb-2 w-32">
        <Select labelText="Embedding" bind:selected={previewEmbedding}>
          {#each $embeddings?.data || [] as emdField}
            <SelectItem value={emdField.name} />
          {/each}
        </Select>
      </div>
    </div>
  </div>
  <div class:border-t={previewText != null} class="mt-4 border-gray-200">
    {#if conceptScore && $conceptScore?.isFetching}
      <SkeletonText />
    {:else if previewResultItem != null && previewText != null}
      <div class="my-2">
        <span class="font-medium">Max score:</span>
        <span class="rounded p-0.5" style:background-color={colorFromScore(maxConceptScore)}
          >{maxConceptScore.toFixed(3)}</span
        >
      </div>
      <StringSpanHighlight
        text={previewText}
        row={previewResultItem}
        {spanPaths}
        {spanValueInfos}
        embeddings={previewEmbedding ? [previewEmbedding] : []}
      />
    {/if}
  </div>
</div>
