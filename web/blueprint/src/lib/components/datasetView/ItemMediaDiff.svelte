<script lang="ts">
  import type * as Monaco from 'monaco-editor/esm/vs/editor/editor.api';
  import {onDestroy, onMount} from 'svelte';

  import {
    DEFAULT_HEIGHT_PEEK_SCROLL_PX,
    DEFAULT_HEIGHT_PEEK_SINGLE_ITEM_PX,
    getMonaco,
    MONACO_OPTIONS
  } from '$lib/monaco';
  import {getDatasetViewContext, type ColumnComparisonState} from '$lib/stores/datasetViewStore';
  import {getDisplayPath} from '$lib/view_utils';
  import {getValueNodes, L, type DatasetUISettings, type LilacValueNode} from '$lilac';
  import {PropertyRelationship} from 'carbon-icons-svelte';
  import {hoverTooltip} from '../common/HoverTooltip';

  const MAX_MONACO_HEIGHT_COLLAPSED = 360;

  const datasetViewStore = getDatasetViewContext();

  export let row: LilacValueNode | undefined | null;
  export let colCompareState: ColumnComparisonState;
  export let textIsOverBudget: boolean;
  export let isExpanded: boolean;
  export let viewType: DatasetUISettings['view_type'] | undefined = undefined;
  export let datasetViewHeight: number | undefined = undefined;
  export let isFetching: boolean | undefined = undefined;

  let editorContainer: HTMLElement;

  $: leftPath = colCompareState.swapDirection
    ? colCompareState.compareToColumn
    : colCompareState.column;
  $: rightPath = colCompareState.swapDirection
    ? colCompareState.column
    : colCompareState.compareToColumn;
  $: leftValue = row != null ? (L.value(getValueNodes(row, leftPath)[0]) as string) : '';
  $: rightValue = row != null ? (L.value(getValueNodes(row, rightPath)[0]) as string) : '';

  let monaco: typeof Monaco;
  let editor: Monaco.editor.IStandaloneDiffEditor;

  $: {
    if (isExpanded != null || row != null) {
      relayout();
    }
  }
  $: maxMonacoHeightCollapsed = datasetViewHeight
    ? datasetViewHeight -
      (viewType === 'scroll' ? DEFAULT_HEIGHT_PEEK_SCROLL_PX : DEFAULT_HEIGHT_PEEK_SINGLE_ITEM_PX)
    : MAX_MONACO_HEIGHT_COLLAPSED;
  function relayout() {
    if (
      editor != null &&
      editor.getModel()?.original != null &&
      editor.getModel()?.modified != null
    ) {
      const contentHeight = Math.max(
        editor.getOriginalEditor().getContentHeight(),
        editor.getModifiedEditor().getContentHeight()
      );
      textIsOverBudget = contentHeight > MAX_MONACO_HEIGHT_COLLAPSED;

      if (isExpanded) {
        editorContainer.style.height = contentHeight + 'px';
      } else if (!textIsOverBudget) {
        editorContainer.style.height = `${Math.min(contentHeight, maxMonacoHeightCollapsed)}px`;
      } else {
        editorContainer.style.height = maxMonacoHeightCollapsed + 'px';
      }
      editor.layout();
    }
  }

  onMount(async () => {
    monaco = await getMonaco();

    editor = monaco.editor.createDiffEditor(editorContainer, {
      ...MONACO_OPTIONS,
      // Turn on line numbers and margins for the diff editor.
      glyphMargin: true,
      lineNumbersMinChars: 3,
      lineNumbers: 'on'
    });

    editor.onDidChangeModel(() => {
      relayout();
    });
  });

  $: {
    if (editor != null && leftValue != null && rightValue != null) {
      editor.setModel({
        original: monaco.editor.createModel(leftValue, 'text/plain'),
        modified: monaco.editor.createModel(rightValue, 'text/plain')
      });
      relayout();
    }
  }

  onDestroy(() => {
    editor.getModel()?.modified.dispose();
    editor.getModel()?.original.dispose();
    editor?.dispose();
  });
</script>

<!-- For reasons unknown to me, the -ml-6 is required to make the autolayout of monaco react. -->
<div class="relative left-16 -ml-10 flex h-fit w-full flex-col gap-x-4 pr-6">
  <div class="flex flex-row items-center font-mono text-xs font-medium text-neutral-500">
    <div class="ml-8 w-1/2">{getDisplayPath(leftPath)}</div>
    <div class="ml-8 w-1/2">{getDisplayPath(rightPath)}</div>
    <div>
      <button
        class="-mr-1 mb-1 flex flex-row"
        on:click={() => datasetViewStore.swapCompareColumn(colCompareState?.column || [])}
        use:hoverTooltip={{text: 'Swap comparison order'}}><PropertyRelationship /></button
      >
    </div>
  </div>
  <div class="editor-container" bind:this={editorContainer} />
  {#if isFetching}
    <div class="absolute inset-0 flex items-center justify-center bg-white bg-opacity-70" />
  {/if}
</div>

<style lang="postcss">
  .editor-container {
    width: 100%;
  }
  :global(.editor-container .monaco-editor .lines-content.monaco-editor-background) {
    margin-left: 10px;
  }
</style>
