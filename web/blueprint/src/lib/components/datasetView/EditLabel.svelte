<script context="module" lang="ts">
  // eslint-disable-next-line @typescript-eslint/no-empty-interface
  export interface LabelsQuery extends Omit<AddLabelsOptions, 'label_name'> {}
</script>

<script lang="ts">
  import {addLabelsMutation, removeLabelsMutation} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getNotificationsContext} from '$lib/stores/notificationsStore';
  import {getSchemaLabels, type AddLabelsOptions, type RemoveLabelsOptions} from '$lilac';
  import {ComboBox, InlineLoading, Modal} from 'carbon-components-svelte';
  import {Tag, type CarbonIcon} from 'carbon-icons-svelte';
  import {createEventDispatcher} from 'svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import {clickOutside} from '../common/clickOutside';

  export let labelsQuery: LabelsQuery;
  export let hideLabels: string[] | undefined = undefined;
  export let helperText = 'Add label';
  export let disabled = false;
  export let disabledMessage = 'User does not have access to add labels.';
  export let icon: typeof CarbonIcon;
  export let remove = false;
  export let totalNumRows: number | undefined = undefined;
  const dispatch = createEventDispatcher();

  let labelMenuOpen = false;
  let comboBox: ComboBox;
  let comboBoxText = '';
  let selectedLabel: string | null = null;

  const notificationStore = getNotificationsContext();

  const datasetStore = getDatasetContext();
  const datasetViewStore = getDatasetViewContext();

  $: namespace = $datasetViewStore.namespace;
  $: datasetName = $datasetViewStore.datasetName;

  const authInfo = queryAuthInfo();
  $: canCreateLabelTypes = $authInfo.data?.access.dataset.create_label_type;
  $: canEditLabels = $authInfo.data?.access.dataset.edit_labels;

  $: schemaLabels = $datasetStore.schema && getSchemaLabels($datasetStore.schema);
  $: newLabelAllowed = /^[A-Za-z0-9_-]+$/.test(comboBoxText) && canCreateLabelTypes;
  $: newLabelItem = {
    id: 'new-label',
    text: comboBoxText,
    disabled: !newLabelAllowed
  };
  $: missingLabelItems =
    schemaLabels
      ?.filter(l => !(hideLabels || []).includes(l))
      .map((l, i) => ({id: `label_${i}`, text: l})) || [];
  $: labelItems = [...(comboBoxText != '' && !remove ? [newLabelItem] : []), ...missingLabelItems];

  $: addLabels = $datasetStore.schema != null ? addLabelsMutation($datasetStore.schema) : null;
  $: removeLabels =
    $datasetStore.schema != null ? removeLabelsMutation($datasetStore.schema) : null;

  $: inProgress = $addLabels?.isLoading || $removeLabels?.isLoading;

  $: disableLabels = disabled || !canEditLabels;

  function addLabel() {
    labelMenuOpen = true;
    requestAnimationFrame(() => {
      // comboBox.clear({focus: true}) does not open the combo box automatically, so we
      // programmatically set it.
      comboBox.$set({open: true});
    });
  }

  interface LabelItem {
    id: 'new-label' | string;
    text: string;
  }

  function editLabels() {
    if (selectedLabel == null) {
      return;
    }
    const options: AddLabelsOptions | RemoveLabelsOptions = {
      ...labelsQuery,
      label_name: selectedLabel
    };
    labelMenuOpen = false;

    function message(numRows: number): string {
      return options.row_ids != null
        ? `Document id: ${options.row_ids}`
        : `${numRows.toLocaleString()} rows updated`;
    }

    if (!remove) {
      $addLabels!.mutate([namespace, datasetName, options], {
        onSuccess: numRows => {
          notificationStore.addNotification({
            kind: 'success',
            title: `Added label "${options.label_name}"`,
            message: message(numRows)
          });
        }
      });
    } else {
      $removeLabels!.mutate([namespace, datasetName, options], {
        onSuccess: numRows => {
          notificationStore.addNotification({
            kind: 'success',
            title: `Removed label "${options.label_name}"`,
            message: message(numRows)
          });
        }
      });
    }
    selectedLabel = null;
  }

  function selectLabelItem(
    e: CustomEvent<{
      selectedItem: LabelItem;
    }>
  ) {
    selectedLabel = e.detail.selectedItem.text;
    comboBox.clear();
    if (totalNumRows == null) {
      editLabels();
    }
  }
</script>

<div
  use:hoverTooltip={{
    text: !canEditLabels ? 'You do not have access to add labels.' : disabled ? disabledMessage : ''
  }}
>
  <button
    disabled={disableLabels || inProgress}
    class:opacity-30={disableLabels}
    class:text-red-600={remove}
    on:click={addLabel}
    use:hoverTooltip={{text: helperText}}
    class="flex items-center gap-x-2 border border-gray-300"
    class:hidden={labelMenuOpen}
  >
    {#if inProgress}
      <InlineLoading />
    {/if}
    <svelte:component this={icon} />
  </button>
</div>
<div
  class="z-50 w-60"
  class:hidden={!labelMenuOpen}
  use:clickOutside={() => (labelMenuOpen = false)}
>
  <ComboBox
    size="sm"
    open={labelMenuOpen}
    bind:this={comboBox}
    items={labelItems}
    bind:value={comboBoxText}
    on:select={selectLabelItem}
    shouldFilterItem={(item, value) =>
      item.text.toLowerCase().includes(value.toLowerCase()) || item.id === 'new-label'}
    placeholder={!remove ? 'Select or type a new label' : 'Select a label to remove'}
    let:item={it}
  >
    {@const item = labelItems.find(p => p.id === it.id)}
    {#if item == null}
      <div />
    {:else if item.id === 'new-label'}
      <div class="new-concept flex flex-row items-center justify-items-center">
        <Tag />
        <div class="ml-2">
          New label: {comboBoxText}
        </div>
      </div>
    {:else}
      <div class="flex justify-between gap-x-8">{item.text}</div>
    {/if}
  </ComboBox>
</div>

<Modal
  size="xs"
  open={selectedLabel != null && totalNumRows != null}
  modalHeading="Label"
  primaryButtonText="Confirm"
  secondaryButtonText="Cancel"
  selectorPrimaryFocus=".bx--btn--primary"
  on:submit={editLabels}
  on:click:button--secondary={() => {
    selectedLabel = null;
    dispatch('close');
  }}
  on:close={(selectedLabel = null)}
>
  <p>
    {#if remove}
      Remove label <span class="font-mono font-bold">{selectedLabel}</span> from {totalNumRows?.toLocaleString()}
      rows?
    {:else}
      Add label <span class="font-mono font-bold">{selectedLabel}</span> to {totalNumRows?.toLocaleString()}
      rows?
    {/if}
  </p>
</Modal>

<style lang="postcss">
  :global(.bx--inline-loading) {
    width: unset !important;
    min-height: unset !important;
  }
</style>
