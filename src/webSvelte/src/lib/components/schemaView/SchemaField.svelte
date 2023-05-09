<script lang="ts">
  import {getDatasetViewContext} from '$lib/store/datasetViewStore';
  import {
    ENTITY_FEATURE_KEY,
    PATH_WILDCARD,
    isSignalField,
    pathIsEqual,
    type LilacSchema,
    type LilacSchemaField,
    type Path
  } from '$lilac';
  import {Checkbox, Tag} from 'carbon-components-svelte';
  import CaretDown from 'carbon-icons-svelte/lib/CaretDown.svelte';
  import {slide} from 'svelte/transition';
  import ContextMenu from '../contextMenu/ContextMenu.svelte';
  import SchemaFieldMenu from '../contextMenu/SchemaFieldMenu.svelte';
  import ExtraColumnField from './ExtraColumnField.svelte';

  export let schema: LilacSchema;
  export let field: LilacSchemaField;
  export let indent = 0;

  // Skip over the repeated field.
  if (field.repeated_field) {
    field = field.repeated_field;
  }

  let datasetViewStore = getDatasetViewContext();

  $: path = field.path;
  $: signalField = isSignalField(field);
  let expanded = true;

  $: isRepeatedField = field.path.at(-1) === PATH_WILDCARD ? true : false;
  $: fieldName = isRepeatedField ? field.path.at(-2) : field.path.at(-1);

  // Fields that have been added in the UI and don't come from the schema
  $: extraColumns = $datasetViewStore.extraColumns.filter(column =>
    // Ignore the entity field at the end of the path.
    pathIsEqual(column.feature.filter(p => p != ENTITY_FEATURE_KEY) as Path, path)
  );

  $: children = childFields(field);
  $: hasChildren = children.length > 0 || extraColumns.length > 0;
  $: isVisible = $datasetViewStore.visibleColumns.some(p => pathIsEqual(p, path));

  // Find all the child paths for a given field.
  function childFields(field?: LilacSchemaField): LilacSchemaField[] {
    if (!field?.fields) return [];

    return (
      Object.values(field.fields)
        // Filter out the entity field.
        .filter(f => f.path.at(-1) != ENTITY_FEATURE_KEY)
    );
  }
</script>

<div
  class="flex w-full flex-row items-center border-b border-solid border-gray-200 py-2 hover:bg-gray-100"
>
  <div class="w-6">
    <Checkbox
      labelText="Show"
      hideLabel
      selected={isVisible}
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
  {#if signalField}
    <div>
      <Tag type="blue">Signal</Tag>
    </div>
  {/if}
  <div class="w-24 pr-2 text-right">{field?.dtype}{isRepeatedField ? '[]' : ''}</div>
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
    {#each extraColumns as column}
      <ExtraColumnField {column} indent={indent + 1} />
    {/each}
  </div>
{/if}
