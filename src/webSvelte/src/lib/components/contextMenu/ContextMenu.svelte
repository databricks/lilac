<script lang="ts">
  import { ThreeDotsVertical } from 'svelte-bootstrap-icons';
</script>

<div class="dropdown">
  <!-- svelte-ignore a11y-no-noninteractive-element-to-interactive-role -->
  <!-- svelte-ignore a11y-label-has-associated-control -->
  <label tabindex="0" role="button" class="hover:opacity-70"><ThreeDotsVertical /> </label>
  <!-- svelte-ignore a11y-no-noninteractive-tabindex -->
  <ul tabindex="0" class="dropdown-content menu rounded-box bg-base-100 w-52 p-2 shadow">
    <slot />
  </ul>
</div>
