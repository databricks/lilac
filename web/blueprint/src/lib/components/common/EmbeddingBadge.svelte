<script lang="ts">
  import {Tag} from 'carbon-components-svelte';
  import {AssemblyCluster} from 'carbon-icons-svelte';

  export let embedding: string | undefined;
</script>

<Tag {...$$restProps} type="purple" slot="icon"
  ><AssemblyCluster class="mr-1 inline-block" />{embedding}</Tag
>
