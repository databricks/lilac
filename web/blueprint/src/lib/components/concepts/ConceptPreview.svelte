<script lang="ts">
  import {queryConceptScore} from '$lib/queries/conceptQueries';
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {
    VALUE_KEY,
    childFields,
    deserializeRow,
    deserializeSchema,
    type Concept,
    type LilacField,
    type LilacSchema,
    type LilacValueNode,
    type Signal
  } from '$lilac';
  import {Button, Select, SelectItem, SkeletonText, TextArea} from 'carbon-components-svelte';
  import StringSpanHighlight from '../datasetView/StringSpanHighlight.svelte';

  export let concept: Concept;

  const embeddings = queryEmbeddings();

  // User entered text.
  let textareaText: string;
  // The text show in the highlight preview.
  let previewText: string | undefined = undefined;
  let previewEmbedding: string | undefined = undefined;
  $: conceptScore =
    previewEmbedding != null && previewText != null
      ? queryConceptScore(concept.namespace, concept.concept_name, previewEmbedding, {
          examples: [{text: previewText}]
        })
      : null;
  function computeConceptScore() {
    previewText = textareaText;
    previewResultItem = undefined;
  }
  $: console.log('conceptScore', conceptScore);

  const PREVIEW_TEXT_FIELD = 'text';

  let resultSchema: LilacSchema | undefined = undefined;
  let previewResultItem: LilacValueNode | undefined = undefined;
  let visibleFields: LilacField<Signal>[] = [];
  let conceptFields: LilacField<Signal>[] = [];
  $: {
    if ($conceptScore?.data != null && previewEmbedding != null) {
      // Create the schema for the preview result. This is required to match the structure we
      // we require in the string span highlighter. That component should be refactored to take a
      // simpler input so we don't have to do this.
      resultSchema = deserializeSchema({
        fields: {
          [PREVIEW_TEXT_FIELD]: {
            dtype: 'string',
            fields: {
              [previewEmbedding]: {
                repeated_field: {
                  dtype: 'string_span',
                  fields: {
                    [`${concept.namespace}/${concept.concept_name}`]: {
                      dtype: 'float32',
                      signal: {
                        signal_name: 'concept_score',
                        embedding: previewEmbedding,
                        namespace: concept.namespace,
                        concept_name: concept.concept_name
                      }
                    }
                  }
                }
              }
            }
          }
        }
      });
      previewResultItem = deserializeRow(
        {
          [PREVIEW_TEXT_FIELD]: {
            [VALUE_KEY]: textareaText,
            [previewEmbedding]: $conceptScore.data.scores
          }
        },
        resultSchema
      );
      visibleFields = childFields(resultSchema);
      conceptFields = [
        resultSchema.fields![PREVIEW_TEXT_FIELD]!.fields![previewEmbedding!].repeated_field!
      ];
    }
  }
</script>

<div class="flex flex-col gap-x-8">
  <div>
    <TextArea
      bind:value={textareaText}
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
    {:else if previewResultItem != null && visibleFields != null && conceptFields != null}
      <StringSpanHighlight
        text={previewText}
        row={previewResultItem}
        {visibleFields}
        visibleKeywordSpanFields={[]}
        visibleSpanFields={conceptFields}
        visibleLabelSpanFields={[]}
      />
    {/if}
  </div>
</div>
