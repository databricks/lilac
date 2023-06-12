<script lang="ts">
  import {
    isOrdinal,
    listFieldParents,
    serializePath,
    type LilacField,
    type LilacSchema,
    type LilacValueNode
  } from '$lilac';
  import RowItemValue from './RowItemValue.svelte';

  export let row: LilacValueNode;
  export let schema: LilacSchema;

  export let visibleFields: LilacField[];

  $: valueFields = visibleFields
    // Skip fields that are not strings or ordinals.
    .filter(f => f.dtype && (isOrdinal(f.dtype) || f.dtype === 'string'))
    // Skip children of string spans. Those are rendered by RowItemValue.
    .filter(f => !listFieldParents(f, schema).some(parent => parent.dtype === 'string_span'));
</script>

<div class="mb-4 flex flex-col gap-y-4 border-b border-gray-300 p-4">
  {#each valueFields as field (serializePath(field.path))}
    <RowItemValue {field} {visibleFields} {row} path={field.path} />
  {/each}
</div>
