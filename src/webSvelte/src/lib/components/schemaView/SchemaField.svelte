<script lang="ts">
  import { getDatasetViewContext } from '$lib/store/datasetViewStore';
  import { LILAC_COLUMN, pathIsEqual, type LilacSchema, type LilacSchemaField } from '$lilac';
  import type { Field } from '$lilac/fastapi_client';
  import { CaretDown, EyeFill, EyeSlashFill } from 'svelte-bootstrap-icons';
  import { slide } from 'svelte/transition';
  import ContextMenu from '../contextMenu/ContextMenu.svelte';
  import SchemaFieldMenu from '../contextMenu/SchemaFieldMenu.svelte';

  export let schema: LilacSchema;
  export let field: LilacSchemaField;
  export let indent = 0;

  let datasetViewStore = getDatasetViewContext();

  let path = field.path;
  let isAnnotation = field.path[0] === LILAC_COLUMN;
  let expanded = true;

  $: hasChildren = !!field?.fields;
  $: children = childFields(field);
  $: isVisible = $datasetViewStore.visibleColumns.some((p) => pathIsEqual(p, path));

  // Find all the child paths for a given field.
  function childFields(field?: Field) {
    if (!field?.fields) return [];
    return Object.values(field.fields);
  }
</script>

<div class="flex w-full flex-row border-b border-solid border-gray-200 py-2 hover:bg-gray-100">
  <div class="w-6">
    <button
      on:click={() => {
        if (isVisible) {
          datasetViewStore.removeVisibleColumn(path);
        } else {
          datasetViewStore.addVisibleColumn(path);
        }
      }}
    >
      {#if isVisible}
        <EyeFill />
      {:else}
        <EyeSlashFill class="opacity-50" />
      {/if}
    </button>
  </div>
  <div class="w-6" style:margin-left={indent * 10 + 'px'}>
    {#if hasChildren}
      <button
        class="transition"
        class:rotate-180={!expanded}
        on:click={() => (expanded = !expanded)}><CaretDown class="w-3" /></button
      >
    {/if}
  </div>
  <div class="grow truncate whitespace-nowrap text-gray-900" class:text-purple-800={isAnnotation}>
    <!-- {path.at(-1)} -->
    {path.join('.')}
    {#if isAnnotation}
      <div class="badge badge-sm badge-primary ml-2">Signal</div>
    {/if}
  </div>
  <div class="w-12">{field?.dtype}</div>
  <div>
    <ContextMenu>
      <SchemaFieldMenu {path} />
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
