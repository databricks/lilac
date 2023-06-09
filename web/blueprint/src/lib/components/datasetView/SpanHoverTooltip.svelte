<script lang="ts">
  import type {SpanHoverNamedValue} from '$lib/view_utils';

  export let namedValues: SpanHoverNamedValue[];
  export let x: number;
  export let y: number;

  const pageWidth = window.innerWidth;
  let width = 0;

  $: console.log(namedValues);
</script>

<div
  role="tooltip"
  class="absolute max-w-fit -translate-y-full break-words border border-gray-300 bg-white p-2 shadow-md"
  style:top="{y}px"
  style:left="{Math.min(x, pageWidth - width - 20)}px"
  bind:clientWidth={width}
>
  <div class="table">
    {#each namedValues as namedValue}
      <div class="table-row">
        <div class="named-value-name table-cell max-w-xs truncate pr-2">{namedValue.name}</div>
        <div class="table-cell">{namedValue.value}</div>
      </div>
    {/each}
  </div>
</div>

<style>
  .named-value-name {
    max-width: 16rem;
  }
</style>
