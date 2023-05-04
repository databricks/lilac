<script lang="ts">
  import { ThreeDotsVertical } from 'svelte-bootstrap-icons';
</script>

<div class="dropdown">
  <label tabindex="0" role="button" class="hover:opacity-70"><ThreeDotsVertical /> </label>
  <ul tabindex="0" class="dropdown-content menu bg-base-100 rounded-box w-52 p-2 shadow">
    <slot />
  </ul>
</div>
