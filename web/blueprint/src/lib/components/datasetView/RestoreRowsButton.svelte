<script lang="ts">
  import {restoreRowsMutation} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import type {DeleteRowsOptions} from '$lilac';
  import {Modal} from 'carbon-components-svelte';
  import {Undo} from 'carbon-icons-svelte';
  import {createEventDispatcher} from 'svelte';
  import {hoverTooltip} from '../common/HoverTooltip';

  export let rowIds: string[] | undefined = undefined;
  export let searches: DeleteRowsOptions['searches'] | undefined = undefined;
  export let filters: DeleteRowsOptions['filters'] | undefined = undefined;
  export let numRows: number | undefined = undefined;

  const dispatch = createEventDispatcher();

  $: {
    if (numRows == null && rowIds != null) {
      numRows = rowIds.length;
    }
  }

  const datasetViewStore = getDatasetViewContext();

  const restoreRows = restoreRowsMutation();
  function restoreClicked() {
    $restoreRows.mutate(
      [
        $datasetViewStore.namespace,
        $datasetViewStore.datasetName,
        {
          row_ids: rowIds,
          searches,
          filters
        }
      ],
      {
        onSuccess: () => {
          dispatch('restore');
          modalOpen = false;
          close();
        }
      }
    );
  }

  let modalOpen = false;
</script>

<button
  use:hoverTooltip={{
    text: rowIds != null && rowIds.length === 1 ? 'Restore deleted row' : 'Restore deleted rows'
  }}
  class="rounded border border-gray-300 bg-white hover:border-gray-500 hover:bg-transparent"
  on:click={() => {
    modalOpen = true;
  }}
>
  <Undo />
</button>

<Modal
  size="xs"
  open={modalOpen}
  modalHeading="Restore rows"
  primaryButtonText="Confirm"
  secondaryButtonText="Cancel"
  selectorPrimaryFocus=".bx--btn--primary"
  on:submit={() => restoreClicked()}
  on:click:button--secondary={() => {
    modalOpen = false;
  }}
  on:close={() => (modalOpen = false)}
>
  <p>
    Restore <span class="font-mono font-bold"> {numRows?.toLocaleString()}</span>
    rows?
  </p>
</Modal>
