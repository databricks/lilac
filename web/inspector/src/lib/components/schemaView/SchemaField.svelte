<script lang="ts">
  import {getDatasetViewContext, isPathVisible} from '$lib/stores/datasetViewStore';
  import {
    PATH_WILDCARD,
    VALUE_KEY,
    getField,
    isSignalField,
    isSignalRootField,
    pathIsEqual,
    type BinaryOp,
    type LilacSchema,
    type LilacSchemaField,
    type ListOp,
    type Path,
    type UnaryOp
  } from '$lilac';
  import {Checkbox, OverflowMenu, Tag} from 'carbon-components-svelte';
  import CaretDown from 'carbon-icons-svelte/lib/CaretDown.svelte';
  import SortAscending from 'carbon-icons-svelte/lib/SortAscending.svelte';
  import SortDescending from 'carbon-icons-svelte/lib/SortDescending.svelte';
  import {slide} from 'svelte/transition';
  import {Command, triggerCommand} from '../commands/Commands.svelte';
  import RemovableTag from '../common/RemovableTag.svelte';
  import SchemaFieldMenu from '../contextMenu/SchemaFieldMenu.svelte';

  export let schema: LilacSchema;
  export let field: LilacSchemaField;
  export let indent = 0;
  export let aliasMapping: Record<string, Path> | undefined;

  const FILTER_SHORTHANDS: Record<BinaryOp | UnaryOp | ListOp, string> = {
    equals: '=',
    not_equal: '!=',
    less: '<',
    less_equal: '<=',
    greater: '>',
    greater_equal: '>=',
    in: 'in',
    exists: 'exists',
    like: 'has'
  };

  let datasetViewStore = getDatasetViewContext();
  let expanded = true;

  $: path = field.path;
  $: alias = field.alias;
  $: parentField = getField(schema, field.path.slice(0, -1));

  $: signalField = isSignalField(field, schema);
  $: signalRoot =
    isRepeatedField && parentField ? isSignalRootField(parentField) : isSignalRootField(field);

  $: isRepeatedField = field.path.at(-1) === PATH_WILDCARD ? true : false;
  $: fieldName = isRepeatedField ? field.path.at(-2) : field.path.at(-1);

  $: children = childFields(field);
  $: hasChildren = children.length > 0;

  $: isVisible = isPathVisible($datasetViewStore.visibleColumns, path, aliasMapping);

  $: isSortedBy = $datasetViewStore.queryOptions.sort_by?.some(p => pathIsEqual(p, alias || path));
  $: sortOrder = $datasetViewStore.queryOptions.sort_order;

  $: filters =
    $datasetViewStore.queryOptions.filters?.filter(f => pathIsEqual(f.path, alias || path)) || [];
  $: isFiltered = filters.length > 0;

  $: disabled = !field.dtype || field.dtype === 'embedding';

  // Find all the child paths for a given field.
  function childFields(field?: LilacSchemaField): LilacSchemaField[] {
    if (!field?.fields) return [];

    return (
      Object.values(field.fields)
        // Filter out the entity field.
        .filter(f => f.path.at(-1) !== VALUE_KEY)
    );
  }

  // Check if any query option columns match the alias
  $: udfColumn = alias
    ? $datasetViewStore.queryOptions.columns?.find(
        c => typeof c === 'object' && !Array.isArray(c) && c.alias === alias?.[0]
      )
    : undefined;
</script>

{#if field.repeated_field}
  <!-- Skip over fields that contain repeated fields -->
  <svelte:self field={field.repeated_field} {indent} {schema} {aliasMapping} />
{:else}
  <div
    class="flex w-full flex-row items-center border-b border-gray-200 px-4 py-2 hover:bg-gray-100"
    class:bg-blue-50={signalField}
    class:hover:bg-blue-100={signalField}
  >
    <div class="w-6">
      <Checkbox
        labelText="Show"
        hideLabel
        checked={isVisible}
        {disabled}
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
          class="p-2 transition hover:opacity-60"
          class:rotate-180={!expanded}
          on:click={() => (expanded = !expanded)}><CaretDown class="w-3" /></button
        >
      {/if}
    </div>
    <div class="grow truncate whitespace-nowrap text-gray-900">
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
        on:remove={() => datasetViewStore.removeSortBy(alias || path)}
      >
        Sorted
        {#if sortOrder == 'ASC'}
          <SortAscending />
        {:else}
          <SortDescending />
        {/if}
      </RemovableTag>
    {/if}
    {#if isFiltered}
      <RemovableTag
        interactive
        type="magenta"
        on:click={() =>
          triggerCommand({
            command: Command.EditFilter,
            namespace: $datasetViewStore.namespace,
            datasetName: $datasetViewStore.datasetName,
            path
          })}
        on:remove={() => datasetViewStore.removeFilters(alias || path)}
      >
        {#if filters.length > 1}
          Filtered
        {:else}
          {FILTER_SHORTHANDS[filters[0].op]} {filters[0].value ?? ''}
        {/if}
      </RemovableTag>
    {/if}
    {#if signalRoot && udfColumn}
      <Tag type="green">Signal Preview</Tag>
    {:else if signalRoot}
      <Tag type="blue">Signal</Tag>
    {/if}
    {#if field?.dtype}
      <div class="w-24 pr-2 text-right">{field.dtype}{isRepeatedField ? '[]' : ''}</div>
    {/if}
    <div>
      <OverflowMenu light flipped>
        <SchemaFieldMenu {field} {schema} />
      </OverflowMenu>
    </div>
  </div>

  <!-- Render child fields -->
  {#if expanded}
    <div transition:slide|local>
      {#if children.length}
        {#each children as childField}
          <svelte:self {schema} field={childField} indent={indent + 1} {aliasMapping} />
        {/each}
      {/if}
    </div>
  {/if}
{/if}
