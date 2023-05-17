<script lang="ts">
  export let title: string;
  export let x: number;
  export let y: number;

  const pageWidth = window.innerWidth;
  let width = 0;
</script>

<div
  role="tooltip"
  class="absolute translate-y-3 whitespace-pre border border-gray-300 bg-white p-2 shadow-md"
  style:top="{y}px"
  style:left="{Math.min(x, pageWidth - width - 20)}px"
  bind:clientWidth={width}
>
  {title}
</div>
