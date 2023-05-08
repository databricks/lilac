<script lang="ts">
  import { notEmpty } from '$lib/utils';
  /**
   * Component that renders string spans as an absolute positioned
   * layer, meant to be rendered on top of the source text.
   */
  import type { DataTypeCasted } from '$lilac';

  export let stringSpans: Array<DataTypeCasted<'string_span'>>;
  export let text: string;

  // All the spans
  let spans = stringSpans.filter(notEmpty);
  let spanStart = 0;

  // Fill up the gaps between the spans
  let filledSpans: Array<{ start: number; end: number; show: boolean }> = [];

  for (const span of spans) {
    if (spanStart != span.start) {
      filledSpans.push({ start: spanStart, end: span.start, show: false });
    }
    filledSpans.push({ start: span.start, end: span.end, show: true });
    spanStart = span.end;
  }
</script>

<div class="pointer-events-none absolute top-0">
  {#each filledSpans as span}<span
      class="bg-yellow-500 text-transparent opacity-0 bg-blend-lighten"
      class:opacity-20={span.show}>{text.slice(span.start, span.end)}</span
    >{/each}
</div>
