<script lang="ts">
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {
    getVisibleFields,
    mergeSpans,
    type MergedSpan,
    type SpanHoverNamedValue
  } from '$lib/view_utils';
  /**
   * Component that renders string spans as an absolute positioned
   * layer, meant to be rendered on top of the source text.
   */
  import {
    L,
    deserializePath,
    formatValue,
    getFieldsByDtype,
    getValueNodes,
    isConceptScoreSignal,
    serializePath,
    valueAtPath,
    type LilacField,
    type LilacValueNode,
    type LilacValueNodeCasted
  } from '$lilac';
  import {spanHover} from './SpanHover';
  import StringSpanDetails from './StringSpanDetails.svelte';

  export let text: string;
  export let row: LilacValueNode;

  // This color comes from tailwind bg-yellow-500.
  const highlightColor = (opacity: number) => `rgba(234,179,8, ${opacity})`;

  let datasetViewStore = getDatasetViewContext();
  let datasetStore = getDatasetContext();

  export let field: LilacField;
  $: visibleFields = getVisibleFields($datasetViewStore, $datasetStore, field);

  // Find the keyword span paths under this field.
  $: keywordSpanPaths = visibleFields
    .filter(f => f.signal?.signal_name === 'substring_search')
    .flatMap(f => getFieldsByDtype('string_span', f))
    .map(f => serializePath(f.path));

  // Find the non-keyword span fields under this field.
  $: spanFields = visibleFields
    .filter(f => f.signal?.signal_name !== 'substring_search')
    .filter(f => f.dtype === 'string_span');

  // Map the span field paths to their children that are floats.
  $: spanFloatFields = Object.fromEntries(
    spanFields.map(f => [serializePath(f.path), getFieldsByDtype('float32', f)])
  );

  const showScoreThreshold = 0.5;
  const minScoreBackgroundOpacity = 0.1;
  const maxScoreBackgroundOpacity = 0.5;
  const spanHoverOpacity = 0.9;

  $: pathToSpans = Object.fromEntries(
    spanFields.map(f => [
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
    mergedSpan: MergedSpan;
  }

  let selectedSpan: MergedSpan | undefined;
  // Store the mouse position after selecting a span so we can keep the details next to the cursor.
  let spanClickMousePosition: {x: number; y: number} | undefined;
  type ConceptTextInfo = {conceptName: string; conceptNamespace: string; text: string};
  let selectedConceptTextInfo: ConceptTextInfo | undefined;
  $: {
    if (selectedSpan != null) {
      const concepts: ConceptTextInfo[] = [];
      // Find the concepts for the selected spans. For now, we select just the first concept.
      for (const spanPath of Object.keys(selectedSpan.originalSpans)) {
        const floatFields = spanFloatFields[spanPath];
        for (const floatField of floatFields) {
          if (isConceptScoreSignal(floatField.signal)) {
            concepts.push({
              conceptName: floatField.signal.concept_name,
              conceptNamespace: floatField.signal.namespace,
              // Currently we don't support overlapping spans, so we choose the text given by the
              // span.
              text: selectedSpan.text
            });
          }
        }
      }
      // Only use the first concept. We will later support multiple concepts.
      selectedConceptTextInfo = concepts[0];
    }
  }

  // Map the merged spans to the information needed to render each span.
  let spanRenderInfos: RenderSpan[];
  $: {
    spanRenderInfos = [];
    for (const mergedSpan of mergedSpans) {
      const isBolded = keywordSpanPaths.some(
        keywordPath => mergedSpan.originalSpans[keywordPath] != null
      );

      const fieldToValue: {[fieldName: string]: string} = {};
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
            const value = L.value<'float32'>(valueAtPath(originalSpan as LilacValueNode, subPath));
            if (value != null) {
              maxScore = Math.max(maxScore, value);
              fieldToValue[floatField.path.at(-1)!] = formatValue(value);
            }
          }
        }
      }

      let opacity = 0.0;
      // If the value has crossed the threshold, lerp the value between (min, max).
      if (maxScore > showScoreThreshold) {
        const normalizedScore = (maxScore - showScoreThreshold) / (1.0 - showScoreThreshold);
        opacity =
          minScoreBackgroundOpacity +
          normalizedScore * (maxScoreBackgroundOpacity - minScoreBackgroundOpacity);
      }

      const hoverInfo: SpanHoverNamedValue[] = Object.entries(fieldToValue).map(
        ([fieldName, value]) => ({name: fieldName, value})
      );

      spanRenderInfos.push({
        backgroundColor: highlightColor(opacity),
        isBolded,
        hoverInfo,
        paths: mergedSpan.paths,
        text: mergedSpan.text,
        mergedSpan
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
</script>

<div class="relative mb-4 whitespace-pre-wrap">
  {#each spanRenderInfos as renderSpan}
    {@const hovered = isHovered(pathsHovered, renderSpan)}
    <span
      use:spanHover={renderSpan.hoverInfo}
      class="relative leading-5 hover:cursor-pointer"
      class:font-bold={renderSpan.isBolded}
      style:background-color={!hovered
        ? renderSpan.backgroundColor
        : highlightColor(spanHoverOpacity)}
      on:mouseenter={() => spanMouseEnter(renderSpan)}
      on:mouseleave={() => spanMouseLeave(renderSpan)}
      on:keydown={e => {
        if (e.key == 'Enter') {
          if (renderSpan.mergedSpan.originalSpans != null) selectedSpan = renderSpan.mergedSpan;
        }
      }}
      on:click={e => {
        if (renderSpan.mergedSpan.originalSpans != null) selectedSpan = renderSpan.mergedSpan;
        spanClickMousePosition = {x: e.offsetX, y: e.offsetY};
      }}>{renderSpan.text}</span
    >
  {/each}
  {#if selectedConceptTextInfo != null}
    <StringSpanDetails
      conceptName={selectedConceptTextInfo.conceptName}
      conceptNamespace={selectedConceptTextInfo.conceptNamespace}
      text={selectedConceptTextInfo.text}
      clickPosition={spanClickMousePosition}
      on:close={() => {
        selectedSpan = undefined;
        selectedConceptTextInfo = undefined;
      }}
    />
  {/if}
</div>
