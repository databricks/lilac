<script lang="ts">
  export let title: string;
  export let x: number;
  export let y: number;
</script>

<div
  class="absolute border border-gray-300 bg-white p-2 shadow-md"
  style:top="{y + 5}px"
  style:left="{x + 5}px"
>
  {title}
</div>
