<script lang="ts">
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {isPreviewSignal} from '$lib/view_utils';
  import {
    L,
    PATH_KEY,
    ROWID,
    SCHEMA_FIELD_KEY,
    VALUE_KEY,
    formatValue,
    getField,
    isLabelField,
    isSignalRootField,
    pathIncludes,
    valueAtPath,
    type DataTypeCasted,
    type LilacField,
    type LilacSelectRowsSchema,
    type LilacValueNode
  } from '$lilac';
  import ItemMetadataField, {type RenderNode} from './ItemMetadataField.svelte';

  export let row: LilacValueNode;
  export let selectRowsSchema: LilacSelectRowsSchema | undefined = undefined;
  export let highlightedFields: LilacField[];

  const embeddings = queryEmbeddings();

  function makeRenderNode(node: LilacValueNode): RenderNode {
    const field = L.field(node)!;
    const path = L.path(node)!;
    let value = L.value(node);
    if (field.dtype === 'string_span') {
      const stringValues = [];
      // Get the parent that is dtype string to resolve the span.
      for (let i = path.length - 1; i >= 0; i--) {
        const parentPath = path.slice(0, i);
        const parent = getField(selectRowsSchema!.schema, parentPath)!;

        if (parent.dtype === 'string') {
          const v = L.value<'string'>(valueAtPath(row, parentPath)!)!;
          const {start, end} = value as {start: number; end: number};
          stringValues.push(v.slice(start, end));
          break;
        }
      }
      value = stringValues as unknown as DataTypeCasted;
    }

    const isEmbeddingSignal =
      $embeddings.data?.some(embedding => embedding.name === field.signal?.signal_name) || false;
    const isSignal = isSignalRootField(field);
    const isLabel = isLabelField(field);
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

    function getChildren(node: LilacValueNode): LilacValueNode[] {
      // Strip internal values.
      /* eslint-disable @typescript-eslint/no-unused-vars */
      const {
        [VALUE_KEY]: _value,
        [PATH_KEY]: _path,
        [SCHEMA_FIELD_KEY]: _field,
        [ROWID]: _rowid,
        ...rest
      } = node;
      /* eslint-enable @typescript-eslint/no-unused-vars */
      // Filter out any label fields.
      return Object.values(rest).filter(n => L.field(n)?.label == null);
    }
    // Expand any parents of highlighted fields.
    const expanded = highlightedFields.some(highlightedField => {
      return pathIncludes(highlightedField.path, path);
    });
    return {
      children: Array.isArray(node)
        ? node.map(makeRenderNode)
        : getChildren(node).map(makeRenderNode),
      fieldName: path[path.length - 1],
      field,
      path,
      expanded,
      isSignal,
      isLabel,
      isPreviewSignal: selectRowsSchema != null ? isPreviewSignal(selectRowsSchema, path) : false,
      isEmbeddingSignal,
      value,
      formattedValue
    };
  }
  $: renderNode = makeRenderNode(row);
</script>

{#each renderNode.children || [] as child}
  <ItemMetadataField node={child} />
{/each}
