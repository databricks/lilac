<script context="module" lang="ts">
  export interface SpanHoverNamedValue {
    name: string;
    value: DataTypeCasted;
    isConcept?: boolean;
    isKeywordSearch?: boolean;
  }
</script>

<script lang="ts">
  import type {DataTypeCasted} from '$lilac';
  import {colorFromScore} from './colors';

  export let namedValues: SpanHoverNamedValue[];
  export let x: number;
  export let y: number;

  const pageWidth = window.innerWidth;
  let width = 0;

  // Leave a single pixel gap between the tooltip and the span to allow the mouse to leave the span
  // when moving upwards to another span.
  const top = y - 1;
</script>

<div
  role="tooltip"
  class:hidden={namedValues.length === 0}
  class="absolute z-50 max-w-fit -translate-y-full break-words border border-gray-300 bg-white px-2 shadow-md"
  style:top="{top}px"
  style:left="{Math.min(x, pageWidth - width - 20)}px"
  bind:clientWidth={width}
>
  <div class="table border-spacing-y-2">
    {#each namedValues as namedValue (namedValue)}
      <div class="table-row">
        <div class="named-value-name table-cell max-w-xs truncate pr-2">{namedValue.name}</div>
        <div class="table-cell rounded text-right">
          <span
            style:background-color={namedValue.isConcept && typeof namedValue.value === 'number'
              ? colorFromScore(namedValue.value)
              : ''}
            class:font-bold={namedValue.isKeywordSearch}
            class="px-1"
          >
            {typeof namedValue.value === 'number'
              ? namedValue.value.toFixed(3)
              : namedValue.value}</span
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
