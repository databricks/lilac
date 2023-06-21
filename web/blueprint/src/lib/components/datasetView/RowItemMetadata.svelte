<script lang="ts">
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {isItemVisible, isPreviewSignal} from '$lib/view_utils';
  import {
    L,
    formatValue,
    isSignalRootField,
    listValueNodes,
    serializePath,
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
    value?: DataTypeCasted;
  }
  function makeRows(row: LilacValueNode): MetadataRow[] {
    const valueNodes = listValueNodes(row).filter(item => isItemVisible(item, visibleFields));
    return valueNodes.map(valueNode => {
      const field = L.field(valueNode)!;
      const path = L.path(valueNode)!;
      let value = L.value(valueNode);
      return {
        indentLevel: path.length - 1,
        fieldName: path[path.length - 1],
        field,
        path,
        isSignal: isSignalRootField(field),
        isPreviewSignal: isPreviewSignal($datasetStore.selectRowsSchema?.data || null, path),
        isEmbeddingSignal:
          $embeddings.data?.some(embedding => embedding.name === field.signal?.signal_name) ||
          false,
        value
      };
    });
  }

  $: rows = makeRows(row);
</script>

{#if rows.length > 0}
  <div class="h-full border-l border-gray-300">
    <table class="mx-2 mt-1 table border-collapse">
      {#each rows as row, i (serializePath(row.path))}
        {@const formattedValue = row.value !== undefined ? formatValue(row.value) : ''}
        <tr class:border-b={i < rows.length - 1} class="border-gray-300">
          <td class="p-2 pl-2 pr-2 font-mono text-xs font-medium text-neutral-500">
            <span style:padding-left={`${row.indentLevel * 12}px`}>{row.fieldName}</span>
          </td>
          <td class="px-2">
            {#if row.isEmbeddingSignal}
              <EmbeddingBadge hideEmbeddingName={true} embedding={row.field.signal?.signal_name} />
            {:else if row.isSignal}
              <SignalBadge isPreview={row.isPreviewSignal} />
            {/if}
          </td>
          <td class="p-2">
            {#if row.value !== undefined}
              <div title={`${row.value}`} class="w-32 truncate pr-2 text-xs">
                {row.value !== undefined ? `${formattedValue}` : ''}
              </div>
            {/if}
          </td>
        </tr>
      {/each}
    </table>
  </div>
{/if}
