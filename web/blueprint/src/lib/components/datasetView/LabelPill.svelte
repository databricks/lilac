<script lang="ts">
  export let label: string;
  export let active: boolean;
  export let disabled = false;

  $: active = active && !disabled;
</script>

<button
  {disabled}
  class="rounded-lg border border-gray-300 hover:border-gray-500"
  class:bg-slate-500={active}
  class:hover:bg-slate-500={active}
  class:hover:bg-transparent={!active}
  class:text-white={active}
  on:click
>
  {label}
</button>
