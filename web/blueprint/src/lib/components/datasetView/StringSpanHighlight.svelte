<script lang="ts">
  /**
   * Component that renders string spans as an absolute positioned
   * layer, meant to be rendered on top of the source text.
   */
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {mergeSpans, type MergedSpan, type SpanHoverNamedValue} from '$lib/view_utils';

  import {
    L,
    deserializePath,
    getFieldsByDtype,
    getValueNodes,
    isConceptScoreSignal,
    pathIsEqual,
    serializePath,
    valueAtPath,
    type LilacField,
    type LilacValueNode,
    type LilacValueNodeCasted,
    type Signal
  } from '$lilac';
  import {spanHover} from './SpanHover';
  import StringSpanDetails, {type SpanDetails} from './StringSpanDetails.svelte';
  import {colorFromOpacity, colorFromScore} from './colors';

  export let text: string;
  export let row: LilacValueNode;
  export let visibleKeywordSpanFields: LilacField[];
  export let visibleSpanFields: LilacField[];

  const spanHoverOpacity = 0.9;

  const datasetStore = getDatasetContext();

  // Find the keyword span paths under this field.
  $: keywordSpanPaths = visibleKeywordSpanFields.map(f => serializePath(f.path));

  // Map the span field paths to their children that are floats.
  $: spanFloatFields = Object.fromEntries(
    visibleSpanFields.map(f => [
      serializePath(f.path),
      getFieldsByDtype('float32', f).filter(f =>
        $datasetStore?.visibleFields?.some(visibleField => pathIsEqual(visibleField.path, f.path))
      )
    ])
  );

  // Filter the floats to only those that are concept scores.
  let spanConceptFields: {[fieldName: string]: LilacField<Signal>[]};
  $: spanConceptFields = Object.fromEntries(
    Object.entries(spanFloatFields)
      .map(([path, fields]) => [path, fields.filter(f => isConceptScoreSignal(f.signal))])
      .filter(([_, fields]) => fields.length > 0)
  );

  // Map a path to the visible span fields.
  $: pathToSpans = Object.fromEntries(
    visibleSpanFields.map(f => [
      serializePath(f.path),
      getValueNodes(row, f.path) as LilacValueNodeCasted<'string_span'>[]
    ])
  );

  // Merge all the spans for different features into a single span array.
  $: mergedSpans = mergeSpans(text, pathToSpans);

  interface RenderSpan {
    backgroundColor: string;
    isBolded: boolean;
    hoverInfo: SpanHoverNamedValue[];
    paths: string[];
    text: string;
    originalSpans: {[spanSet: string]: LilacValueNodeCasted<'string_span'>[]};
  }

  // Map the merged spans to the information needed to render each span.
  let spanRenderInfos: RenderSpan[];
  $: {
    spanRenderInfos = [];
    for (const mergedSpan of mergedSpans) {
      const isBolded = keywordSpanPaths.some(
        keywordPath => mergedSpan.originalSpans[keywordPath] != null
      );

      // Map field names to all their values.
      const fieldToValue: {[fieldName: string]: number} = {};
      // Compute the maximum score for all original spans matching this render span to choose the
      // color.
      let maxScore = -Infinity;
      for (const [spanPathStr, originalSpans] of Object.entries(mergedSpan.originalSpans)) {
        const floatFields = spanFloatFields[spanPathStr];
        const spanPath = deserializePath(spanPathStr);
        if (floatFields.length === 0) continue;

        for (const originalSpan of originalSpans) {
          for (const floatField of floatFields) {
            const subPath = floatField.path.slice(spanPath.length);
            const value = valueAtPath(originalSpan as LilacValueNode, subPath);
            if (value == null) continue;
            const floatValue = L.value<'float32'>(value);
            if (floatValue != null) {
              maxScore = Math.max(maxScore, floatValue);
              fieldToValue[floatField.path.at(-1)!] = floatValue;
            }
          }
        }
      }

      // Show all float values in the hover tooltip.
      const hoverInfo: SpanHoverNamedValue[] = Object.entries(fieldToValue).map(
        ([fieldName, value]) => ({name: fieldName, value})
      );

      spanRenderInfos.push({
        backgroundColor: colorFromScore(maxScore),
        isBolded,
        hoverInfo,
        paths: mergedSpan.paths,
        text: mergedSpan.text,
        originalSpans: mergedSpan.originalSpans
      });
    }
  }

  // Map each of the paths to their render spans so we can highlight neighbors on hover when there
  // is overlap.
  let pathToRenderSpans: {[pathStr: string]: Array<MergedSpan>} = {};
  $: {
    pathToRenderSpans = {};
    for (const renderSpan of mergedSpans) {
      for (const path of renderSpan.paths) {
        pathToRenderSpans[path] = pathToRenderSpans[path] || [];
        pathToRenderSpans[path].push(renderSpan);
      }
    }
  }

  // Span hover.
  let pathsHovered: Set<string> = new Set();
  const spanMouseEnter = (renderSpan: RenderSpan) => {
    renderSpan.paths.forEach(path => pathsHovered.add(path));
    pathsHovered = pathsHovered;
  };
  const spanMouseLeave = (renderSpan: RenderSpan) => {
    renderSpan.paths.forEach(path => pathsHovered.delete(path));
    pathsHovered = pathsHovered;
  };
  const isHovered = (pathsHovered: Set<string>, renderSpan: RenderSpan): boolean => {
    return renderSpan.paths.some(path => pathsHovered.has(path));
  };

  // Span selection via a click.
  let selectedSpan: RenderSpan | undefined;
  let selectedSpanDetails: SpanDetails | undefined;
  // Store the mouse position after selecting a span so we can keep the details next to the cursor.
  let spanClickMousePosition: {x: number; y: number} | undefined;
  $: {
    if (selectedSpan != null) {
      selectedSpanDetails = {
        conceptName: null,
        conceptNamespace: null,
        text: selectedSpan.text
      };
      // Find the concepts for the selected spans. For now, we select just the first concept.
      for (const spanPath of Object.keys(selectedSpan.originalSpans)) {
        for (const conceptField of spanConceptFields[spanPath] || []) {
          // Only use the first concept. We will later support multiple concepts.
          selectedSpanDetails.conceptName = conceptField.signal!.concept_name;
          selectedSpanDetails.conceptNamespace = conceptField.signal!.namespace;
          break;
        }
      }
    } else {
      selectedSpanDetails = undefined;
    }
  }
</script>

<div class="relative mb-4 whitespace-pre-wrap">
  {#each spanRenderInfos as renderSpan}
    {@const hovered = isHovered(pathsHovered, renderSpan)}
    <span
      use:spanHover={renderSpan.hoverInfo}
      class="hover:cursor-poiner highlight-span text-sm leading-5"
      class:hover:cursor-pointer={visibleSpanFields.length > 0}
      class:font-bold={renderSpan.isBolded}
      style:background-color={!hovered
        ? renderSpan.backgroundColor
        : colorFromOpacity(spanHoverOpacity)}
      on:mouseenter={() => spanMouseEnter(renderSpan)}
      on:mouseleave={() => spanMouseLeave(renderSpan)}
      on:keydown={e => {
        if (e.key == 'Enter') {
          if (renderSpan.originalSpans != null && visibleSpanFields.length > 0)
            selectedSpan = renderSpan;
        }
      }}
      on:click={e => {
        if (renderSpan.originalSpans != null && visibleSpanFields.length > 0)
          selectedSpan = renderSpan;
        spanClickMousePosition = {x: e.offsetX, y: e.offsetY};
      }}>{renderSpan.text}</span
    >
  {/each}
  {#if selectedSpanDetails != null}
    <StringSpanDetails
      details={selectedSpanDetails}
      clickPosition={spanClickMousePosition}
      on:close={() => {
        selectedSpan = undefined;
      }}
      on:click={() => {
        selectedSpan = undefined;
      }}
    />
  {/if}
</div>

<style>
  .highlight-span {
    /** Add a tiny bit of padding so that the hover doesn't flicker between rows. */
    padding-top: 1px;
  }
</style>
