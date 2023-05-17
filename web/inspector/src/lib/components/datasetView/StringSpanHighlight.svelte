<script lang="ts">
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
    isFloat,
    listFields,
    pathIsEqual,
    type LilacSchemaField,
    type LilacValueNode,
    type Path
  } from '$lilac';
  import {tooltip} from '../common/tootltip';

  export let text: string;
  export let stringSpanFields: Array<LilacSchemaField>;
  export let row: LilacValueNode;
  export let visibleColumns: Path[];

  $: spans = stringSpanFields.flatMap(f => getValueNodes(row, f.path));

  // Fill up the gaps between the spans
  let filledSpans: Array<{
    start: number;
    end: number;
    show: boolean;
    properties?: Array<LilacValueNode>;
  }> = [];

  $: {
    filledSpans = [];
    let spanStart = 0;
    for (const span of spans) {
      const spanValue = L.value<'string_span'>(span);
      const valuePath = L.path(span);
      if (!spanValue || !valuePath) continue;

      // Add filler
      if (spanStart != spanValue.start) {
        filledSpans.push({start: spanStart, end: spanValue.start, show: false});
      }

      // Find all sub fields to the span so we can show their value in the tooltip
      const children = listFields(L.field(span))
        .slice(1)
        // Filter out non-visible columns
        .filter(field => visibleColumns.some(c => pathIsEqual(c, field.path)))
        // Replace the path with prefix of the path with value path that includes index instead of wildcard
        .map(field => ({
          ...field,
          path: [...valuePath, ...field.path.slice(valuePath.length)]
        }))
        // Get the value nodes for each child
        .flatMap(field => getValueNode(span, field.path))
        .filter(notEmpty);

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
        }
      }

      filledSpans.push({
        start: spanValue.start,
        end: spanValue.end,
        show,
        properties: children
      });
      spanStart = spanValue.end;
    }
  }

  function tooltipText(span: (typeof filledSpans)[number]) {
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
        title={tooltipText(span)}
        class="bg-yellow-500 text-transparent opacity-0 hover:opacity-30"
        class:opacity-10={span.show}
        class:hover:opacity-40={span.show}>{text.slice(span.start, span.end)}</span
      >{/each}
  </div>
</div>
