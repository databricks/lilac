<script context="module" lang="ts">
  // eslint-disable-next-line @typescript-eslint/no-empty-interface
  export interface LabelsQuery extends Omit<AddLabelsOptions, 'label_name'> {}
</script>

<script lang="ts">
  import {
    addLabelsMutation,
    queryDatasetSchema,
    removeLabelsMutation
  } from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getNotificationsContext} from '$lib/stores/notificationsStore';
  import {getSchemaLabels, type AddLabelsOptions, type RemoveLabelsOptions} from '$lilac';
  import {Modal} from 'carbon-components-svelte';
  import {Tag, type CarbonIcon} from 'carbon-icons-svelte';
  import {createEventDispatcher} from 'svelte';
  import ButtonDropdown from '../ButtonDropdown.svelte';

  export let labelsQuery: LabelsQuery;
  export let hideLabels: string[] | undefined = undefined;
  export let helperText = 'Add label';
  export let disabled = false;
  export let disabledMessage = 'User does not have access to add labels.';
  export let icon: typeof CarbonIcon;
  export let remove = false;
  export let totalNumRows: number | undefined = undefined;
  const dispatch = createEventDispatcher();

  let comboBoxText = '';
  let selectedLabel: string | null = null;

  const notificationStore = getNotificationsContext();

  const datasetViewStore = getDatasetViewContext();
  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: namespace = $datasetViewStore.namespace;
  $: datasetName = $datasetViewStore.datasetName;

  const authInfo = queryAuthInfo();
  $: canCreateLabelTypes = $authInfo.data?.access.dataset.create_label_type;
  $: canEditLabels = $authInfo.data?.access.dataset.edit_labels;

  $: schemaLabels = $schema.data && getSchemaLabels($schema.data);
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

  $: addLabels = $schema.data != null ? addLabelsMutation($schema.data) : null;
  $: removeLabels = $schema.data != null ? removeLabelsMutation($schema.data) : null;

  $: inProgress = $addLabels?.isLoading || $removeLabels?.isLoading;

  $: disableLabels = disabled || !canEditLabels;

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

  function selectLabelItem(e: CustomEvent<LabelItem>) {
    selectedLabel = e.detail.text;
    if (totalNumRows == null) {
      editLabels();
    }
  }
</script>

<ButtonDropdown
  disabled={disableLabels || inProgress}
  {helperText}
  disabledMessage={!canEditLabels
    ? 'You do not have access to add labels.'
    : disabled
    ? disabledMessage
    : ''}
  hoist={false}
  buttonOutline
  buttonIcon={icon}
  bind:comboBoxText
  on:select={selectLabelItem}
  items={labelItems}
  comboBoxPlaceholder={!remove ? 'Select or type a new label' : 'Select a label to remove'}
  shouldFilterItem={(item, value) =>
    item.text.toLowerCase().includes(value.toLowerCase()) || item.id === 'new-label'}
>
  <div slot="item" let:item let:inputText>
    {#if item == null}
      <div />
    {:else if item.id === 'new-label'}
      <div class="new-concept flex flex-row items-center justify-items-center">
        <Tag />
        <div class="ml-2">
          New label: {inputText}
        </div>
      </div>
    {:else}
      <div class="flex justify-between gap-x-8">{item.text}</div>
    {/if}
  </div>
</ButtonDropdown>

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
