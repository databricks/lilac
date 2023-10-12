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
  import {ComboBox} from 'carbon-components-svelte';
  import {Tag, type CarbonIcon} from 'carbon-icons-svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import {clickOutside} from '../common/clickOutside';

  export let labelsQuery: LabelsQuery;
  export let hideLabels: string[] | undefined = undefined;
  export let helperText = 'Add label';
  export let disabled = false;
  export let disabledMessage = 'User does not have access to add labels.';
  export let icon: typeof CarbonIcon;
  export let remove = false;

  $: labelMenuOpen = false;
  let comboBox: ComboBox;
  let comboBoxText = '';

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

  const selectLabelItem = (
    e: CustomEvent<{
      selectedId: LabelItem['id'];
      selectedItem: LabelItem;
    }>
  ) => {
    const selectedItem = e.detail.selectedItem;
    const options: AddLabelsOptions | RemoveLabelsOptions = {
      ...labelsQuery,
      label_name: selectedItem.text
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
    comboBox.clear();
  };
</script>

<div
  use:hoverTooltip={{
    text: !canEditLabels ? 'You do not have access to add labels.' : disabled ? disabledMessage : ''
  }}
>
  <button
    disabled={disableLabels}
    class:opacity-30={disableLabels}
    class:bg-red-100={remove}
    on:click={addLabel}
    use:hoverTooltip={{text: helperText}}
    class="flex items-center gap-x-2 border border-gray-300"
    class:hidden={labelMenuOpen}
  >
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
