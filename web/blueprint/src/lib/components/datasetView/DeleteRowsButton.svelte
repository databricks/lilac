<script lang="ts">
  import {deleteRowsMutation} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import type {DeleteRowsOptions} from '$lilac';
  import {Modal} from 'carbon-components-svelte';
  import {TrashCan} from 'carbon-icons-svelte';
  import {createEventDispatcher} from 'svelte';
  import {hoverTooltip} from '../common/HoverTooltip';

  export let rowIds: string[] | undefined = undefined;
  export let searches: DeleteRowsOptions['searches'] | undefined = undefined;
  export let filters: DeleteRowsOptions['filters'] | undefined = undefined;
  export let numRows: number | undefined = undefined;
  export let modalOpen = false;

  const authInfo = queryAuthInfo();
  $: canDeleteRows = $authInfo.data?.access.dataset.delete_rows;

  const dispatch = createEventDispatcher();

  $: {
    if (numRows == null && rowIds != null) {
      numRows = rowIds.length;
    }
  }

  const datasetViewStore = getDatasetViewContext();

  const deleteRows = deleteRowsMutation();
  function deleteClicked() {
    $deleteRows.mutate(
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
          dispatch('deleted');
          modalOpen = false;
          close();
        }
      }
    );
  }

  // Disable when no rows are selected and no searches or filters are applied to avoid accidentally
  // deleting everything.
  $: disabled = !canDeleteRows || (rowIds == null && searches == null && filters == null);
</script>

<div
  use:hoverTooltip={{
    text: canDeleteRows
      ? rowIds != null && rowIds.length === 1
        ? 'Delete row'
        : 'Delete rows'
      : 'User does not have access to delete rows.'
  }}
>
  <button
    {disabled}
    class:opacity-30={disabled}
    class="h-8 rounded border border-gray-300 bg-white hover:border-red-500 hover:bg-transparent"
    on:click={() => {
      if (disabled) return;
      modalOpen = true;
    }}
  >
    <TrashCan />
  </button>
</div>
<Modal
  size="xs"
  open={modalOpen && !disabled}
  modalHeading="Delete rows"
  primaryButtonText="Confirm"
  secondaryButtonText="Cancel"
  selectorPrimaryFocus=".bx--btn--primary"
  on:submit={() => deleteClicked()}
  on:click:button--secondary={() => {
    modalOpen = false;
  }}
  on:close={() => (modalOpen = false)}
>
  <p>
    Delete <span class="font-mono font-bold"> {numRows?.toLocaleString()}</span>
    rows?
  </p>
</Modal>
