<script context="module" lang="ts">
  export interface SpanHoverNamedValue {
    info: SpanValueInfo;
    value: DataTypeCasted;
    specificPath: Path;
  }
</script>

<script lang="ts">
  import {isNumeric, type DataTypeCasted, type Path} from '$lilac';
  import {colorFromScore} from './colors';
  import type {SpanValueInfo} from './spanHighlight';

  export let namedValues: SpanHoverNamedValue[];
  export let x: number;
  export let y: number;

  const pageWidth = window.innerWidth;
  let width = 0;

  // Leave a single pixel gap between the tooltip and the span to allow the mouse to leave the span
  // when moving upwards to another span.
  const top = y - 1;

  function displayValue(namedValue: SpanHoverNamedValue) {
    if (typeof namedValue.value === 'number') {
      return namedValue.value.toFixed(3);
    }
    if (namedValue.info.dtype.type === 'string_span') {
      return 'true';
    }
    return namedValue.value;
  }
</script>

<div
  role="tooltip"
  class:hidden={namedValues.length === 0}
  class="absolute max-w-fit -translate-y-full break-words border border-gray-300 bg-white px-2 shadow-md"
  style:top="{top}px"
  style:left="{Math.min(x, pageWidth - width - 20)}px"
  bind:clientWidth={width}
>
  <div class="table border-spacing-y-2">
    {#each namedValues as namedValue (namedValue)}
      <div class="table-row">
        <div class="named-value-name table-cell max-w-xs truncate pr-2">{namedValue.info.name}</div>
        <div class="table-cell rounded text-right">
          <span
            style:background-color={(namedValue.info.type === 'concept_score' ||
              namedValue.info.type === 'semantic_similarity') &&
            typeof namedValue.value === 'number'
              ? colorFromScore(namedValue.value)
              : ''}
            class:font-bold={namedValue.info.type === 'keyword' ||
              (namedValue.info.type === 'metadata' && !isNumeric(namedValue.info.dtype))}
            class="px-1"
          >
            {displayValue(namedValue)}</span
          >
        </div>
      </div>
    {/each}
  </div>
</div>

<style>
  .named-value-name {
    max-width: 15rem;
  }
</style>
