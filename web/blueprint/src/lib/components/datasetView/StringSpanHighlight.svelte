<script lang="ts">
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {notEmpty} from '$lib/utils';
  import {isPathVisible} from '$lib/view_utils';
  /**
   * Component that renders string spans as an absolute positioned
   * layer, meant to be rendered on top of the source text.
   */
  import {
    L,
    childFields,
    formatValue,
    getValueNode,
    getValueNodes,
    isConceptScoreSignal,
    isFloat,
    type ConceptScoreSignal,
    type LilacField,
    type LilacValueNode
  } from '$lilac';
  import {tooltip} from '../common/tootltip';
  import StringSpanDetails from './StringSpanDetails.svelte';

  export let text: string;
  export let stringSpanFields: Array<LilacField>;
  export let keywordSearchSpanFields: Array<LilacField>;
  export let row: LilacValueNode;

  interface AnnotatedStringSpan {
    /** The start character of the span */
    start: number;
    /** The end character of the span */
    end: number;
    /** Whether to show the span */
    show: boolean;
    /** The score value. */
    score: number;
    /** Whether this span is a filler span (no interactions) */
    filler: boolean;
    /** The sub-properties of the span */
    properties?: Array<LilacValueNode>;
    /** The concepts associated with the span */
    concepts?: Array<ConceptScoreSignal>;
  }

  interface AnnotatedSearchSpan {
    /** The start character of the span */
    start: number;
    /** The end character of the span */
    end: number;
    /** Whether to show the span */
    show: boolean;
    /** Whether this span is a filler span (no interactions) */
    filler: boolean;
  }

  let datasetViewStore = getDatasetViewContext();
  let datasetStore = getDatasetContext();

  const showScoreThreshold = 0.5;
  const maxScoreBackgroundOpacity = 0.5;

  let selectedSpan: AnnotatedStringSpan | undefined;
  // Store the mouse position after selecting a span so we can keep the details next to the cursor.
  let spanClickMousePosition: {x: number; y: number} | undefined;

  $: spans = stringSpanFields.flatMap(f => getValueNodes(row, f.path));
  $: searchSpans = keywordSearchSpanFields.flatMap(f => getValueNodes(row, f.path));

  // Fill up the gaps between the spans.
  let filledSpans: Array<AnnotatedStringSpan> = [];

  $: {
    filledSpans = [];
    let spanStart = 0;
    for (const span of spans) {
      const spanValue = L.value<'string_span'>(span);
      const valuePath = L.path(span);
      if (!spanValue || !valuePath) continue;

      // Add filler.
      if (spanStart != spanValue.start) {
        filledSpans.push({
          start: spanStart,
          end: spanValue.start,
          score: 0.0,
          show: false,
          filler: true
        });
      }

      // Find all sub fields to the span so we can show their value in the tooltip.
      const children = childFields(L.field(span))
        .slice(1)
        // Filter out non-visible columns
        .filter(field => isPathVisible($datasetViewStore, $datasetStore, field.path))
        // Replace the path with prefix of the path with value path that includes index instead of wildcard.
        .map(field => ({
          ...field,
          path: [...valuePath, ...field.path.slice(valuePath.length)]
        }))
        // Get the value nodes for each child
        .flatMap(field => getValueNode(span, field.path))
        .filter(notEmpty);

      let concepts: AnnotatedStringSpan['concepts'] = [];
      let show = true;
      let maxScore = 0.0;
      // If any children are floats, use that to determine if we should show the span.
      if (children.some(c => c && isFloat(L.dtype(c)))) {
        show = false;
        for (const child of children) {
          if (isFloat(L.dtype(child))) {
            const score = L.value<'float32'>(child) ?? 0;
            maxScore = Math.max(score, maxScore);
            if (maxScore > showScoreThreshold) {
              show = true;
            }
          }

          const signal = L.field(child)?.signal;
          if (isConceptScoreSignal(signal)) {
            concepts.push(signal);
          }
        }
      }

      filledSpans.push({
        start: spanValue.start,
        end: spanValue.end,
        show,
        score: maxScore,
        properties: children,
        filler: false,
        concepts
      });
      spanStart = spanValue.end;
    }
  }

  // Create the search specific spans, filling gaps like we do for regular spans.
  let filledSearchSpans: Array<AnnotatedSearchSpan> = [];

  $: {
    filledSearchSpans = [];
    let spanStart = 0;
    for (const searchSpan of searchSpans) {
      const spanValue = L.value<'string_span'>(searchSpan);
      const valuePath = L.path(searchSpan);
      if (!spanValue || !valuePath) continue;

      // Add filler.
      if (spanStart != spanValue.start) {
        filledSearchSpans.push({
          start: spanStart,
          end: spanValue.start,
          show: false,
          filler: true
        });
      }

      filledSearchSpans.push({
        start: spanValue.start,
        end: spanValue.end,
        show: true,
        filler: false
      });
      spanStart = spanValue.end;
    }
  }

  function tooltipText(span: AnnotatedStringSpan) {
    if (!span.properties) return '';
    return span.properties
      .map(p => {
        const fieldName = L.path(p)?.at(-1);
        const value = formatValue(L.value(p) ?? '');
        if (value == '') return null;
        return `${fieldName} = ${value}`;
      })
      .filter(p => p != null)
      .join('\n');
  }
</script>

<div class="relative mb-4 leading-5">
  <div class="absolute top-0 w-full">
    {#each filledSearchSpans as span}
      <span
        use:tooltip
        role="button"
        class="border-b-2 border-b-black text-transparent"
        tabindex="0"
        class:border-b-2={span.show}
      >
        {text.slice(span.start, span.end)}
      </span>
    {/each}
  </div>
  <div class="relative top-0 h-full w-full">
    {text}
  </div>
  <div class="absolute top-0 w-full">
    {#each filledSpans as span}
      <!-- Linear scale opacity based on score. -->
      {@const opacity = Math.max(span.score - showScoreThreshold, 0) * maxScoreBackgroundOpacity}
      <span
        use:tooltip
        role="button"
        tabindex="0"
        on:keydown={e => {
          if (e.key == 'Enter') {
            if (!span.filler) selectedSpan = span;
          }
        }}
        on:click={e => {
          if (!span.filler) selectedSpan = span;
          spanClickMousePosition = {x: e.offsetX, y: e.offsetY};
        }}
        title={tooltipText(span)}
        class="relative bg-yellow-500 text-transparent opacity-0 hover:!opacity-30"
        class:bg-green-500={selectedSpan == span}
        class:hover:bg-yellow-600={true}
        style:opacity
        class:hover:!opacity-40={/* Override the inline style opacity on hover. */ true}
        >{text.slice(span.start, span.end)}
      </span>
      {#if selectedSpan == span}
        <StringSpanDetails
          conceptName={(span.concepts || [])[0]?.concept_name}
          conceptNamespace={(span.concepts || [])[0]?.namespace}
          text={text.slice(span.start, span.end)}
          clickPosition={spanClickMousePosition}
          on:close={() => (selectedSpan = undefined)}
        />
      {/if}
    {/each}
  </div>
</div>
