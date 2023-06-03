<script lang="ts">
  import {Tag} from 'carbon-components-svelte';
  import {AssemblyCluster} from 'carbon-icons-svelte';

  export let embedding: string | undefined;
</script>

<Tag {...$$restProps} type="purple" slot="icon">
  <div class="flex flex-row whitespace-nowrap">
    <AssemblyCluster class="mr-2" />
    {embedding}
  </div>
</Tag>
