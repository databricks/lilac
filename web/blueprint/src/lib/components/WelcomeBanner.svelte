<script lang="ts">
  import {goto} from '$app/navigation';
  import {Launch} from 'carbon-icons-svelte';

  export let link: string;
  export let title: string;
  export let backgroundColorClass: string;
</script>

<div class="welcome-item mt-8 w-full rounded shadow-md">
  <div
    class={`flex cursor-pointer flex-row justify-between ${backgroundColorClass} rounded-t px-4 py-4 font-semibold`}
    on:click={() => goto(link)}
    on:keypress={() => goto(link)}
  >
    {title}
    <div><Launch /></div>
  </div>
  <div class="px-4 py-5">
    <slot />
  </div>
</div>
