<script lang="ts">
  import {addLabelsMutation} from '$lib/queries/datasetQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getNotificationsContext} from '$lib/stores/notificationsStore';
  import {
    L,
    ROWID,
    getRowLabels,
    getSchemaLabels,
    serializePath,
    valueAtPath,
    type AddLabelsOptions,
    type BinaryFilter,
    type LilacField,
    type LilacValueNode
  } from '$lilac';
  import {ComboBox, SkeletonText, Tag} from 'carbon-components-svelte';
  import {Add} from 'carbon-icons-svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import {clickOutside} from '../common/clickOutside';
  import ItemMedia from './ItemMedia.svelte';
  import ItemMetadata from './ItemMetadata.svelte';

  export let row: LilacValueNode;
  export let mediaFields: LilacField[];
  export let highlightedFields: LilacField[];

  const datasetStore = getDatasetContext();
  const datasetViewStore = getDatasetViewContext();
  const notificationStore = getNotificationsContext();

  $: namespace = $datasetViewStore.namespace;
  $: datasetName = $datasetViewStore.datasetName;

  const MIN_METADATA_HEIGHT_PX = 320;
  let mediaHeight = 0;

  interface LabelItem {
    id: 'new-label' | string;
    text: string;
  }

  // ComboBox for labeling.
  let labelMenuOpen = false;
  let labelItems: LabelItem[] = [];
  let comboBox: ComboBox;
  let comboBoxText = '';
  const addLabels = addLabelsMutation();

  $: selectRowsSchema = $datasetStore.selectRowsSchema?.data;

  $: schemaLabels = $datasetStore.schema && getSchemaLabels($datasetStore.schema);
  $: rowLabels = getRowLabels(row);
  $: newLabelItem = {
    id: 'new-label',
    text: comboBoxText
  };
  $: missingLabelItems =
    schemaLabels
      ?.filter(l => !rowLabels.includes(l))
      .map((l, i) => ({id: `label_${i}`, text: l})) || [];
  $: labelItems = [...(comboBoxText != '' ? [newLabelItem] : []), ...missingLabelItems];

  function addLabel() {
    labelMenuOpen = true;
    requestAnimationFrame(() => {
      comboBox.clear({focus: true});
    });
  }

  const selectLabelItem = (
    e: CustomEvent<{
      selectedId: LabelItem['id'];
      selectedItem: LabelItem;
    }>
  ) => {
    const selectedItem = e.detail.selectedItem;
    const rowId = L.value(valueAtPath(row, [ROWID])!, 'string')!;
    const filter: BinaryFilter = {path: ROWID, op: 'equals', value: rowId};
    const body: AddLabelsOptions = {
      label_name: selectedItem.text,
      label_value: 'true',
      filters: [filter]
    };
    $addLabels.mutate([namespace, datasetName, body], {
      onSuccess: () => {
        notificationStore.addNotification({
          kind: 'success',
          title: `Added label "${body.label_name}"`,
          message: `Document id: ${rowId}`
        });
        labelMenuOpen = false;
      }
    });
    comboBox.clear();
  };
</script>

<div class="flex flex-col rounded border border-neutral-300 md:flex-row">
  <div class="flex flex-col gap-y-1 p-4 md:w-2/3" bind:clientHeight={mediaHeight}>
    <div class="flex flex-wrap gap-x-2 gap-y-2">
      {#each rowLabels as label}
        <div class="flex items-center rounded-full bg-neutral-200 px-3 py-1 text-neutral-600">
          {label}
        </div>
      {/each}
      <div class="relative h-8">
        <button
          on:click={addLabel}
          use:hoverTooltip={{text: 'Add label'}}
          class="flex items-center gap-x-2 border border-gray-300"
          class:hidden={labelMenuOpen}
          ><Add />
        </button>
        <div
          class="absolute left-0 top-0 w-60"
          class:hidden={!labelMenuOpen}
          use:clickOutside={() => (labelMenuOpen = false)}
        >
          {#if $addLabels.isLoading}
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
      </div>
    </div>
    {#if mediaFields.length > 0}
      {#each mediaFields as mediaField, i (serializePath(mediaField.path))}
        <div
          class:border-b={i < mediaFields.length - 1}
          class:pb-2={i < mediaFields.length - 1}
          class="flex h-full w-full border-neutral-200"
        >
          <ItemMedia {row} path={mediaField.path} field={mediaField} {highlightedFields} />
        </div>
      {/each}
    {/if}
  </div>
  <div class="flex h-full bg-neutral-100 md:w-1/3">
    <div class="sticky top-0 w-full self-start">
      <div
        style={`max-height: ${Math.max(MIN_METADATA_HEIGHT_PX, mediaHeight)}px`}
        class="overflow-y-auto py-2"
      >
        <ItemMetadata {row} {selectRowsSchema} {highlightedFields} />
      </div>
    </div>
  </div>
</div>
