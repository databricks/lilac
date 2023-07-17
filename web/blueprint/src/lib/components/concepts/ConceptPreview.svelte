<script lang="ts">
  import {queryConceptScore} from '$lib/queries/conceptQueries';
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {getSettingsContext} from '$lib/stores/settingsStore';
  import {
    PATH_WILDCARD,
    deserializeRow,
    deserializeSchema,
    type Concept,
    type Example,
    type LilacValueNode,
    type Path,
    type Signal
  } from '$lilac';
  import {Button, Select, SelectItem, SkeletonText, TextArea} from 'carbon-components-svelte';
  import StringSpanHighlight from '../datasetView/StringSpanHighlight.svelte';
  import type {SpanValueInfo} from '../datasetView/spanHighlight';

  export let concept: Concept;
  export let example: Example;

  const embeddings = queryEmbeddings();
  const settings = getSettingsContext();

  // User entered text.
  let textAreaText = example.text?.trim();

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

  // The text show in the highlight preview.
  let previewText: string | undefined = undefined;
  let previewEmbedding = $settings.embedding;
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
  let spanPaths: Path[];
  let valuePaths: SpanValueInfo[];
  $: conceptKey = `${concept.namespace}/${concept.concept_name}`;
  $: {
    if (previewEmbedding != null) {
      spanPaths = [[previewEmbedding, PATH_WILDCARD]];
      valuePaths = [
        {
          spanPath: [previewEmbedding, PATH_WILDCARD],
          path: [previewEmbedding, PATH_WILDCARD, conceptKey],
          name: conceptKey,
          type: 'concept_score',
          dtype: 'float32',
          signal: {
            signal_name: 'concept_scorer',
            concept_name: concept.concept_name,
            namespace: concept.namespace
          } as Signal
        }
      ];
    }
  }
  $: {
    if ($conceptScore?.data != null && previewEmbedding != null) {
      const resultSchema = deserializeSchema({
        fields: {
          [previewEmbedding]: {
            repeated_field: {
              dtype: 'string_span',
              fields: {
                [conceptKey]: {
                  dtype: 'float32'
                }
              }
            }
          }
        }
      });
      previewResultItem = deserializeRow($conceptScore.data.scores[0], resultSchema);
    }
  }
</script>

<div class="flex flex-col gap-x-8">
  <div>
    <TextArea
      value={textAreaText}
      on:input={textChanged}
      cols={50}
      placeholder="Paste text to test the concept."
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
    {#if $conceptScore?.isFetching}
      <SkeletonText />
    {:else if previewResultItem != null && previewText != null}
      <StringSpanHighlight text={previewText} row={previewResultItem} {spanPaths} {valuePaths} />
    {/if}
  </div>
</div>
