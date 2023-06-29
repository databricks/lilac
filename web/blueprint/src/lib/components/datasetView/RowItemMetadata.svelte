<script lang="ts">
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {isItemVisible, isPreviewSignal} from '$lib/view_utils';
  import {
    L,
    formatValue,
    getField,
    isSignalRootField,
    listValueNodes,
    serializePath,
    valueAtPath,
    type DataTypeCasted,
    type LilacField,
    type LilacValueNode,
    type Path
  } from '$lilac';
  import EmbeddingBadge from './EmbeddingBadge.svelte';
  import SignalBadge from './SignalBadge.svelte';

  export let row: LilacValueNode;
  export let visibleFields: LilacField[];

  const datasetStore = getDatasetContext();
  const embeddings = queryEmbeddings();

  interface MetadataRow {
    indentLevel: number;
    fieldName: string;
    field: LilacField;
    isSignal: boolean;
    isPreviewSignal: boolean;
    isEmbeddingSignal: boolean;
    path: Path;
    value?: DataTypeCasted | null;
    formattedValue?: string | null;
  }
  function makeRows(row: LilacValueNode): MetadataRow[] {
    const valueNodes = listValueNodes(row).filter(item => isItemVisible(item, visibleFields));
    return valueNodes.map(valueNode => {
      const field = L.field(valueNode)!;
      const path = L.path(valueNode)!;
      let value = L.value(valueNode);
      if (field.dtype === 'string_span') {
        // Walk upwards to find the parent that has dtype text so we can get the values for the
        // string span.
        for (let i = path.length - 1; i > 0; i--) {
          const parentPath = path.slice(0, i);
          const parentField = getField(L.field(row)!, parentPath);
          if (parentField?.dtype === 'string') {
            const text = L.value<'string'>(valueAtPath(row, parentField.path)!);
            const span = L.value<'string_span'>(valueNode);
            if (span == null) break;
            value = text?.substring(span.start, span.end);
          }
        }
      }
      const isEmbeddingSignal =
        $embeddings.data?.some(embedding => embedding.name === field.signal?.signal_name) || false;
      const isSignal = isSignalRootField(field);
      let formattedValue: string | null;
      if (
        isEmbeddingSignal ||
        (isSignal && field.dtype == null) ||
        field.dtype === 'embedding' ||
        field.repeated_field != null
      ) {
        formattedValue = '';
      } else if (value == null) {
        formattedValue = null;
      } else {
        formattedValue = formatValue(value);
      }

      return {
        indentLevel: path.length - 1,
        fieldName: path[path.length - 1],
        field,
        path,
        isSignal,
        isPreviewSignal: isPreviewSignal($datasetStore.selectRowsSchema?.data || null, path),
        isEmbeddingSignal,
        value,
        formattedValue
      };
    });
  }

  $: rows = makeRows(row);
</script>

{#if rows.length > 0}
  <div class="h-full border-l border-gray-300 bg-neutral-50 py-2">
    <table class="table w-full table-fixed border-collapse px-2 pt-1">
      {#each rows as row (serializePath(row.path))}
        <tr class="border-gray-300">
          <td class="truncate p-2 pl-2 pr-2 font-mono text-xs font-medium text-neutral-500">
            <span title={row.fieldName} style:padding-left={`${row.indentLevel * 12}px`}
              >{row.fieldName}</span
            >
          </td>
          <td class="w-10">
            {#if row.isEmbeddingSignal}
              <EmbeddingBadge hideEmbeddingName={true} embedding={row.field.signal?.signal_name} />
            {:else if row.isSignal}
              <SignalBadge isPreview={row.isPreviewSignal} />
            {/if}
          </td>
          <td class="p-2">
            <div
              title={`${row.value}`}
              class="truncate pr-2 text-xs"
              class:italic={row.formattedValue === null}
            >
              {row.formattedValue}
            </div>
          </td>
        </tr>
      {/each}
    </table>
  </div>
{/if}
