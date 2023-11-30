<script lang="ts">
  import type * as Monaco from 'monaco-editor/esm/vs/editor/editor.api';
  import {onDestroy, onMount} from 'svelte';

  import {getMonaco} from '$lib/monaco';
  import {getDatasetViewContext, type ColumnComparisonState} from '$lib/stores/datasetViewStore';
  import {getDisplayPath} from '$lib/view_utils';
  import {L, getValueNodes, type LilacValueNode} from '$lilac';
  import {PropertyRelationship} from 'carbon-icons-svelte';
  import {hoverTooltip} from '../common/HoverTooltip';

  const MAX_MONACO_HEIGHT = 350;

  const datasetViewStore = getDatasetViewContext();

  export let row: LilacValueNode;
  export let colCompareState: ColumnComparisonState;
  export let textIsOverBudget: boolean;
  export let isExpanded: boolean;

  let editorContainer: HTMLElement;

  $: leftPath = colCompareState.swapDirection
    ? colCompareState.compareToColumn
    : colCompareState.column;
  $: rightPath = colCompareState.swapDirection
    ? colCompareState.column
    : colCompareState.compareToColumn;
  $: leftValue = L.value(getValueNodes(row, leftPath)[0]) as string;
  $: rightValue = L.value(getValueNodes(row, rightPath)[0]) as string;

  let monaco: typeof Monaco;
  let editor: Monaco.editor.IStandaloneDiffEditor;

  $: {
    if (isExpanded != null) {
      relayout();
    }
  }
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
      textIsOverBudget = contentHeight > MAX_MONACO_HEIGHT;

      if (isExpanded || !textIsOverBudget) {
        editorContainer.style.height = `${contentHeight}px`;
      } else {
        editorContainer.style.height = MAX_MONACO_HEIGHT + 'px';
      }
      editor.layout();
    }
  }
  onMount(async () => {
    monaco = await getMonaco();

    editor = monaco.editor.createDiffEditor(editorContainer, {
      readOnly: true,
      lineNumbers: 'on',
      renderFinalNewline: 'dimmed',
      lineDecorationsWidth: 0,
      glyphMargin: true,
      folding: false,
      lineNumbersMinChars: 3,
      roundedSelection: true,
      domReadOnly: true,
      scrollBeyondLastLine: false,
      wordWrap: 'on',
      wrappingStrategy: 'advanced',
      readOnlyMessage: {value: ''},
      scrollbar: {
        verticalScrollbarSize: 8
      },
      minimap: {
        enabled: true,
        side: 'right'
      },

      automaticLayout: true
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
    monaco?.editor.getModels().forEach(model => model.dispose());
    editor?.dispose();
  });
</script>

<div class="relative -ml-6 flex h-fit w-full flex-col gap-x-4">
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
</div>

<style lang="postcss">
  :global(.editor-container) {
    width: 100%;
  }
  :global(.editor-container .monaco-editor .lines-content.monaco-editor-background) {
    margin-left: 10px;
  }
</style>
