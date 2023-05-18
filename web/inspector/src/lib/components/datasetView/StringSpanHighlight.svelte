<script lang="ts">
  import {isPathVisible} from '$lib/stores/datasetViewStore';
  import {notEmpty} from '$lib/utils';
  /**
   * Component that renders string spans as an absolute positioned
   * layer, meant to be rendered on top of the source text.
   */
  import {
    L,
    formatValue,
    getValueNode,
    getValueNodes,
    isConceptScoreSignal,
    isFloat,
    listFields,
    type ConceptScoreSignal,
    type LilacSchemaField,
    type LilacValueNode,
    type Path
  } from '$lilac';
  import {tooltip} from '../common/tootltip';
  import StringSpanHighlightConceptPicker from './StringSpanHighlightConceptPicker.svelte';

  export let text: string;
  export let stringSpanFields: Array<LilacSchemaField>;
  export let row: LilacValueNode;
  export let visibleColumns: Path[];
  export let aliasMapping: Record<string, Path> | undefined;

  interface AnnotatedStringSpan {
    /** The start character of the span */
    start: number;
    /** The end character of the span */
    end: number;
    /** Whether to show the span */
    show: boolean;
    /** Whether this span is a filler span (no interactions) */
    filler: boolean;
    /** The sub-properties of the span */
    properties?: Array<LilacValueNode>;
    /** The concepts associated with the span */
    concepts?: Array<ConceptScoreSignal>;
  }

  let selectedSpan: AnnotatedStringSpan | undefined;

  $: spans = stringSpanFields.flatMap(f => getValueNodes(row, f.path));

  // Fill up the gaps between the spans
  let filledSpans: Array<AnnotatedStringSpan> = [];

  $: {
    filledSpans = [];
    let spanStart = 0;
    for (const span of spans) {
      const spanValue = L.value<'string_span'>(span);
      const valuePath = L.path(span);
      if (!spanValue || !valuePath) continue;

      // Add filler
      if (spanStart != spanValue.start) {
        filledSpans.push({start: spanStart, end: spanValue.start, show: false, filler: true});
      }

      // Find all sub fields to the span so we can show their value in the tooltip
      const children = listFields(L.field(span))
        .slice(1)
        // Filter out non-visible columns
        .filter(field => isPathVisible(visibleColumns, field.path, aliasMapping))
        // Replace the path with prefix of the path with value path that includes index instead of wildcard
        .map(field => ({
          ...field,
          path: [...valuePath, ...field.path.slice(valuePath.length)]
        }))
        // Get the value nodes for each child
        .flatMap(field => getValueNode(span, field.path))
        .filter(notEmpty);

      let concepts: AnnotatedStringSpan['concepts'] = [];
      let show = true;
      // If any children are floats, use that to determine if we should show the span
      if (children.some(c => c && isFloat(L.dtype(c)))) {
        show = false;
        for (const child of children) {
          if (isFloat(L.dtype(child))) {
            if ((L.value<'float32'>(child) ?? 0) > 0.5) {
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
        properties: children,
        filler: false,
        concepts
      });
      spanStart = spanValue.end;
    }
  }

  function tooltipText(span: AnnotatedStringSpan) {
    if (!span.properties) return '';
    return span.properties
      .map(p => `${L.path(p)?.at(-1)} = ${formatValue(L.value(p) ?? '')}`)
      .join('\n');
  }
</script>

<div class="relative leading-5">
  {text}
  <div class=" absolute top-0 w-full">
    {#each filledSpans as span}<span
        use:tooltip
        role="button"
        tabindex="0"
        on:keydown={e => {
          if (e.key == 'Enter') {
            if (!span.filler && span.concepts?.length) selectedSpan = span;
          }
        }}
        on:click={() => {
          if (!span.filler && span.concepts?.length) selectedSpan = span;
        }}
        title={tooltipText(span)}
        class="relative bg-yellow-500 text-transparent opacity-0 hover:opacity-30"
        class:bg-green-500={selectedSpan == span}
        class:opacity-10={span.show}
        class:opacity-40={selectedSpan == span}
        class:hover:opacity-40={span.show}>{text.slice(span.start, span.end)}</span
      >{#if selectedSpan == span && span.concepts?.length}<StringSpanHighlightConceptPicker
          conceptName={span.concepts[0].concept_name}
          conceptNamespace={span.concepts[0].namespace}
          text={text.slice(span.start, span.end)}
          on:close={() => (selectedSpan = undefined)}
        />{/if}{/each}
  </div>
</div>
