<script lang="ts">
  import {
    L,
    PATH_KEY,
    SCHEMA_FIELD_KEY,
    VALUE_KEY,
    childFields,
    pathIsEqual,
    serializePath,
    type DataTypeCasted,
    type LilacField,
    type LilacValueNode,
    type Path
  } from '$lilac';

  export let row: LilacValueNode;
  export let mediaFields: LilacField[];
  export let visibleFields: LilacField[];

  interface MetadataRow {
    indentLevel: number;
    fieldName: string;
    path: Path;
    value?: DataTypeCasted;
  }

  function hasMetadataChildren(field: LilacField): boolean {
    if (field == null) return false;
    return childFields(field).some(
      f =>
        f.dtype != null &&
        f.dtype != 'string_span' &&
        f.dtype != 'embedding' &&
        f != field &&
        visibleFields.some(vf => pathIsEqual(f.path, vf.path))
    );
  }
  function makeRows(row: LilacValueNode): MetadataRow[] {
    const rows: MetadataRow[] = [];
    const rowsToProcess: [string, LilacValueNode, number][] = [];
    for (const [fieldName, childRow] of Object.entries(row || {})) {
      if (visibleFields.some(vf => pathIsEqual(L.path(childRow), vf.path))) {
        rowsToProcess.push([fieldName, childRow, 0]);
      }
    }

    while (rowsToProcess.length > 0) {
      const [fieldName, row, indentLevel] = rowsToProcess.pop()!;
      if (!visibleFields.some(vf => pathIsEqual(L.path(row), vf.path))) {
        continue;
      }

      if (row == null) continue;

      const field = L.field(row)!;
      const isMedia = mediaFields.some(mf => pathIsEqual(mf.path, L.path(row)!));
      let rowHasChildren = hasMetadataChildren(field);
      if (Array.isArray(row)) {
        for (const [i, childRow] of row.entries()) {
          rowsToProcess.push([`${fieldName}[${i}]`, childRow, indentLevel + 1]);
        }
      } else if (typeof row === 'object') {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const {[VALUE_KEY]: value, [PATH_KEY]: path, [SCHEMA_FIELD_KEY]: field, ...rest} = row;

        for (const [childFieldName, childRow] of Object.entries(rest)) {
          rowsToProcess.push([childFieldName, childRow, indentLevel + 1]);
        }
      }
      const rowPath = L.path(row)!;
      let value = L.value(row);
      if (mediaFields.some(mf => pathIsEqual(mf.path, rowPath))) {
        value = undefined;
      }
      // Ignore items with no children.
      if ((field.dtype == null || isMedia) && !rowHasChildren) {
        continue;
      }
      rows.push({indentLevel, fieldName, value, path: rowPath});
    }
    return rows;
  }

  $: rows = makeRows(row);
</script>

{#if rows.length > 0}
  <div class="h-full border-l border-gray-200">
    <table class="mx-2 mt-1 table border-collapse">
      {#each rows as row, i (serializePath(row.path))}
        <tr class:border-b={i < rows.length - 1} class="border-gray-200">
          <td class="p-2 pl-2 pr-6 font-mono text-xs font-medium text-neutral-500">
            <span style:padding-left={`${row.indentLevel * 12}px`}>{row.fieldName}</span>
          </td>
          <td class="p-2">
            {#if row.value !== undefined}
              <div title={`${row.value}`} class="w-32 truncate pr-2 text-xs">
                {row.value !== undefined ? `${row.value}` : ''}
              </div>
            {/if}
          </td>
        </tr>
      {/each}
    </table>
  </div>
{/if}
