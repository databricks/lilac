<script lang="ts">
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {
    PATH_WILDCARD,
    VALUE_FEATURE_KEY,
    isSignalField,
    pathIsEqual,
    type LilacSchema,
    type LilacSchemaField,
    type Path
  } from '$lilac';
  import {Checkbox, Tag} from 'carbon-components-svelte';
  import CaretDown from 'carbon-icons-svelte/lib/CaretDown.svelte';
  import SortAscending from 'carbon-icons-svelte/lib/SortAscending.svelte';
  import SortDescending from 'carbon-icons-svelte/lib/SortDescending.svelte';
  import {slide} from 'svelte/transition';
  import RemovableTag from '../common/RemovableTag.svelte';
  import ContextMenu from '../contextMenu/ContextMenu.svelte';
  import SchemaFieldMenu from '../contextMenu/SchemaFieldMenu.svelte';

  export let schema: LilacSchema;
  export let field: LilacSchemaField;
  export let indent = 0;

  let datasetViewStore = getDatasetViewContext();

  $: path = field.path;
  $: signalField = isSignalField(field, schema);
  let expanded = true;

  $: isRepeatedField = field.path.at(-1) === PATH_WILDCARD ? true : false;
  $: fieldName = isRepeatedField ? field.path.at(-2) : field.path.at(-1);

  $: children = childFields(field);
  $: hasChildren = children.length > 0;

  $: isVisible = $datasetViewStore.visibleColumns.some(p => pathIsEqual(p, path));
  $: isSortedBy = $datasetViewStore.queryOptions.sort_by?.some(p => pathIsEqual(p as Path, path));
  $: sortOrder = $datasetViewStore.queryOptions.sort_order;

  // Find all the child paths for a given field.
  function childFields(field?: LilacSchemaField): LilacSchemaField[] {
    if (!field?.fields) return [];

    return (
      Object.values(field.fields)
        // Filter out the entity field.
        .filter(f => f.path.at(-1) !== VALUE_FEATURE_KEY)
    );
  }
</script>

{#if field.repeated_field}
  <!-- Skip over fields that contain repeated fields -->
  <svelte:self field={field.repeated_field} {indent} {schema} />
{:else}
  <div
    class="flex w-full flex-row items-center border-b border-gray-200 px-4 py-2 hover:bg-gray-100"
  >
    <div class="w-6">
      <Checkbox
        labelText="Show"
        hideLabel
        checked={isVisible}
        disabled={!field?.dtype}
        on:check={ev => {
          if (ev.detail) {
            datasetViewStore.addVisibleColumn(path);
          } else {
            datasetViewStore.removeVisibleColumn(path);
          }
        }}
      />
    </div>
    <div class="w-6" style:margin-left={indent * 24 + 'px'}>
      {#if hasChildren}
        <button
          class="transition"
          class:rotate-180={!expanded}
          on:click={() => (expanded = !expanded)}><CaretDown class="w-3" /></button
        >
      {/if}
    </div>
    <div class="grow truncate whitespace-nowrap text-gray-900" class:text-blue-600={signalField}>
      {fieldName}
    </div>
    {#if isSortedBy}
      <RemovableTag
        interactive
        type="green"
        on:click={() =>
          sortOrder === 'ASC'
            ? ($datasetViewStore.queryOptions.sort_order = 'DESC')
            : ($datasetViewStore.queryOptions.sort_order = 'ASC')}
        on:remove={() => datasetViewStore.removeSortBy(path)}
      >
        Sorted
        {#if sortOrder == 'ASC'}
          <SortAscending />
        {:else}
          <SortDescending />
        {/if}
      </RemovableTag>
    {/if}
    {#if signalField}
      <Tag type="blue">Signal</Tag>
    {/if}

    <div class="w-24 pr-2 text-right">{field?.dtype || ''}{isRepeatedField ? '[]' : ''}</div>
    <div>
      <ContextMenu>
        <SchemaFieldMenu {field} />
      </ContextMenu>
    </div>
  </div>

  <!-- Render child fields -->
  {#if expanded}
    <div transition:slide|local>
      {#if children.length}
        {#each children as childField}
          <svelte:self {schema} field={childField} indent={indent + 1} />
        {/each}
      {/if}
    </div>
  {/if}
{/if}
