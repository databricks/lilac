<script lang="ts">
  import {restoreRowsMutation} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
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

  const authInfo = queryAuthInfo();
  $: canRestoreRows = $authInfo.data?.access.dataset.delete_rows;

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

<div
  class="ml-2 inline-block"
  use:hoverTooltip={{
    text: canRestoreRows
      ? rowIds != null && rowIds.length === 1
        ? 'Restore deleted row'
        : 'Restore deleted rows'
      : 'User does not have access to restore rows.'
  }}
>
  <button
    class:opacity-30={!canRestoreRows}
    disabled={!canRestoreRows}
    class="rounded border border-gray-300 bg-white hover:border-gray-500 hover:bg-transparent"
    on:click={() => {
      modalOpen = true;
    }}
  >
    <Undo />
  </button>
</div>

<Modal
  size="xs"
  open={modalOpen && canRestoreRows}
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
