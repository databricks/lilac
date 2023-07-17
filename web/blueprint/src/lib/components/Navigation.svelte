<script lang="ts">
  import {DataBase, Home, Light, Settings} from 'carbon-icons-svelte';
  import NavigationButton from './NavigationButton.svelte';
</script>

<div class="flex w-full flex-col items-center pt-2">
  <NavigationButton href="/" title="Home" icon={Home} />
  <NavigationButton href="/concepts" title="Concepts" icon={Light} />
  <NavigationButton href="/datasets" title="Datasets" icon={DataBase} />
  <NavigationButton href="/settings" title="Settings" icon={Settings} />
</div>
