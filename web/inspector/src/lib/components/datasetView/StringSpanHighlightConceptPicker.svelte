<script lang="ts">
  /**
   * Component that allows picking concept samples from string spans
   */

  import {fade} from 'svelte/transition';

  import {editConceptMutation} from '$lib/queries/conceptQueries';
  import ThumbsDownFilled from 'carbon-icons-svelte/lib/ThumbsDownFilled.svelte';
  import ThumbsUpFilled from 'carbon-icons-svelte/lib/ThumbsUpFilled.svelte';
  import {createEventDispatcher} from 'svelte';
  import {clickOutside} from '../common/clickOutside';

  export let text: string;
  export let conceptName: string;
  export let conceptNamespace: string;

  const conceptEdit = editConceptMutation();
  const dispatch = createEventDispatcher();
  function addLabel(label: boolean) {
    $conceptEdit.mutate([conceptNamespace, conceptName, {insert: [{text, label}]}]);
  }
</script>

<div
  use:clickOutside={() => dispatch('close')}
  transition:fade={{duration: 60}}
  class="absolute z-10 inline-flex -translate-x-12 translate-y-4 flex-col gap-y-4 divide-gray-200 rounded border border-gray-200 bg-white p-3 shadow"
>
  <button on:click={() => addLabel(true)}>
    <ThumbsUpFilled />
  </button>
  <button on:click={() => addLabel(false)}>
    <ThumbsDownFilled />
  </button>
</div>
