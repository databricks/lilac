<script lang="ts">
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {isItemVisible, isPreviewSignal} from '$lib/view_utils';
  import {
    L,
    formatValue,
    isSignalRootField,
    listValueNodes,
    pathIncludes,
    serializePath,
    type DataTypeCasted,
    type LilacField,
    type LilacSelectRowsSchema,
    type LilacValueNode,
    type Path
  } from '$lilac';
  import EmbeddingBadge from './EmbeddingBadge.svelte';
  import SignalBadge from './SignalBadge.svelte';

  export let row: LilacValueNode;
  export let visibleFields: LilacField[];
  export let selectRowsSchema: LilacSelectRowsSchema | undefined = undefined;

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
    const spanPaths = valueNodes
      .filter(valueNode => L.field(valueNode)?.dtype === 'string_span')
      .map(valueNode => L.path(valueNode)!);
    return (
      valueNodes
        // Filter out any nodes with a span parent. These are rendered with the media.
        .filter(valueNode => {
          return !spanPaths.some(path => pathIncludes(L.path(valueNode)!, path));
        })
        .map(valueNode => {
          const field = L.field(valueNode)!;
          const path = L.path(valueNode)!;
          let value = L.value(valueNode);
          if (field.dtype === 'string_span') {
            // Skip rendering string spans.
            return null;
          }

          const isEmbeddingSignal =
            $embeddings.data?.some(embedding => embedding.name === field.signal?.signal_name) ||
            false;
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
            isPreviewSignal:
              selectRowsSchema != null ? isPreviewSignal(selectRowsSchema, path) : false,
            isEmbeddingSignal,
            value,
            formattedValue
          };
        })
        .filter(x => x != null) as MetadataRow[]
    );
  }

  $: rows = makeRows(row);
</script>

{#if rows.length > 0}
  <div class="border-t border-neutral-200 px-2 py-4">
    <table class="table w-full table-fixed border-collapse px-2 pt-1">
      {#each rows as row (serializePath(row.path))}
        <tr class="border-gray-300">
          <td class="truncate p-2 font-mono text-xs font-medium text-neutral-500">
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
