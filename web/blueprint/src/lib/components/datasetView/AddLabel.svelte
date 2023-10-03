<script context="module" lang="ts">
  // eslint-disable-next-line @typescript-eslint/no-empty-interface
  export interface AddLabelsQuery extends Omit<AddLabelsOptions, 'label_name'> {}
</script>

<script lang="ts">
  import {addLabelsMutation} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getNotificationsContext} from '$lib/stores/notificationsStore';
  import {getSchemaLabels, type AddLabelsOptions} from '$lilac';
  import {ComboBox, SkeletonText} from 'carbon-components-svelte';
  import {Add, Tag} from 'carbon-icons-svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import {clickOutside} from '../common/clickOutside';

  export let addLabelsQuery: AddLabelsQuery;
  export let hideLabels: string[] | undefined = undefined;
  export let buttonText: string | undefined = undefined;
  export let helperText = 'Add label';
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
  $: labelItems = [...(comboBoxText != '' ? [newLabelItem] : []), ...missingLabelItems];

  $: addLabels = $datasetStore.schema != null ? addLabelsMutation($datasetStore.schema) : null;

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
    const addLabelsOptions: AddLabelsOptions = {
      ...addLabelsQuery,
      label_name: selectedItem.text
    };
    $addLabels!.mutate([namespace, datasetName, addLabelsOptions], {
      onSuccess: numRows => {
        const message =
          addLabelsOptions.row_ids != null
            ? `Document id: ${addLabelsOptions.row_ids}`
            : `${numRows.toLocaleString()} rows labeled`;

        notificationStore.addNotification({
          kind: 'success',
          title: `Added label "${addLabelsOptions.label_name}"`,
          message
        });
        labelMenuOpen = false;
      }
    });
    comboBox.clear();
  };
</script>

<div
  class="w-full"
  use:hoverTooltip={{
    text: !canEditLabels ? 'You do not have access to add labels.' : ''
  }}
>
  <button
    disabled={!canEditLabels}
    class:opacity-30={!canEditLabels}
    on:click={addLabel}
    use:hoverTooltip={{text: helperText}}
    class="flex items-center gap-x-2 border border-gray-300"
    class:hidden={labelMenuOpen}
    ><Add />
    {#if buttonText != null}
      <span class="mr-1">{buttonText}</span>
    {/if}
  </button>
</div>
<div
  class="absolute left-0 top-0 w-60"
  class:hidden={!labelMenuOpen}
  use:clickOutside={() => (labelMenuOpen = false)}
>
  {#if $addLabels == null || $addLabels.isLoading}
    <SkeletonText />
  {:else}
    <ComboBox
      size="sm"
      open={labelMenuOpen}
      bind:this={comboBox}
      items={labelItems}
      bind:value={comboBoxText}
      on:select={selectLabelItem}
      shouldFilterItem={(item, value) =>
        item.text.toLowerCase().includes(value.toLowerCase()) || item.id === 'new-label'}
      placeholder="Select or add a new label"
      let:item={it}
    >
      {@const item = labelItems.find(p => p.id === it.id)}
      {#if item == null}
        <div />
      {:else if item.id === 'new-label'}
        <div class="new-concept flex flex-row items-center justify-items-center">
          <Tag><Add /></Tag>
          <div class="ml-2">
            New label: {comboBoxText}
          </div>
        </div>
      {:else}
        <div class="flex justify-between gap-x-8">{item.text}</div>
      {/if}
    </ComboBox>
  {/if}
</div>
