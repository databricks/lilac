<script lang="ts">
  import type * as Monaco from 'monaco-editor/esm/vs/editor/editor.api';
  import {onDestroy, onMount} from 'svelte';

  import {getMonaco} from '$lib/monaco';
  import {getDatasetViewContext, type ColumnComparisonState} from '$lib/stores/datasetViewStore';
  import {getNavigationContext} from '$lib/stores/navigationStore';
  import {SIDEBAR_TRANSITION_TIME_MS, displayPath} from '$lib/view_utils';
  import {L, getValueNodes, type LilacValueNode} from '$lilac';
  import {PropertyRelationship} from 'carbon-icons-svelte';
  import {derived} from 'svelte/store';
  import {hoverTooltip} from '../common/HoverTooltip';

  const MAX_MONACO_HEIGHT_PX = 800;
  const MONACO_PADDING_PX = 19;

  const navStore = getNavigationContext();
  const datasetViewStore = getDatasetViewContext();

  export let row: LilacValueNode;
  export let colCompareState: ColumnComparisonState;

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

  export const showMetadataPanel = derived(datasetViewStore, $store => $store.showMetadataPanel);
  export const swapCompareColumn = derived(
    datasetViewStore,
    $store => $store.compareColumns.find(col => col == colCompareState)?.swapDirection
  );
  let isEditorInitialized = false;

  swapCompareColumn.subscribe(() => (isEditorInitialized = false));

  function relayout() {
    if (editor != null && isEditorInitialized) {
      editor.layout();
    }
  }
  onMount(async () => {
    monaco = await getMonaco();
    editor = monaco.editor.createDiffEditor(editorContainer, {
      readOnly: true,
      lineNumbers: 'off',
      renderFinalNewline: 'dimmed',
      glyphMargin: true,
      lineDecorationsWidth: 0,
      roundedSelection: true,
      domReadOnly: true,
      scrollBeyondLastLine: false,
      wordWrap: 'on',
      wrappingStrategy: 'advanced',
      readOnlyMessage: {value: ''}
    });
    editor.onDidChangeModel(() => {
      editorContainer.style.height =
        Math.min(
          MAX_MONACO_HEIGHT_PX,
          Math.max(
            editor
              .getOriginalEditor()
              .getTopForLineNumber(editor.getModel()!.original.getLineCount()),
            editor
              .getModifiedEditor()
              .getTopForLineNumber(editor.getModel()!.modified.getLineCount())
          )
        ) +
        MONACO_PADDING_PX +
        'px';
      editor.layout();

      // When any of the sidebar panels are opened or closed, we need to re-layout the editor as the
      // size has changed.
      const DELAY_TIME_MS = 50;
      navStore.subscribe(() => setTimeout(relayout, SIDEBAR_TRANSITION_TIME_MS + DELAY_TIME_MS));
      showMetadataPanel.subscribe(() =>
        setTimeout(relayout, SIDEBAR_TRANSITION_TIME_MS + DELAY_TIME_MS)
      );
    });
    window.addEventListener('resize', relayout);

    return () => {
      window.removeEventListener('resize', relayout);
    };
  });
  $: {
    if (editor != null && leftValue != null && rightValue != null && !isEditorInitialized) {
      editor.setModel({
        original: monaco.editor.createModel(leftValue, 'text/plain'),
        modified: monaco.editor.createModel(rightValue, 'text/plain')
      });

      isEditorInitialized = true;
    }
  }

  onDestroy(() => {
    monaco?.editor.getModels().forEach(model => model.dispose());
    editor?.dispose();
  });
</script>

<div class="relative flex h-fit w-full flex-col gap-x-4">
  <div class="flex flex-row items-center font-mono text-xs font-medium text-neutral-500">
    <div class="w-1/2">{displayPath(leftPath)}</div>
    <div class="ml-4 w-1/2">{displayPath(rightPath)}</div>
    <div>
      <button
        class="mb-1 mr-3 flex flex-row"
        on:click={() => datasetViewStore.swapCompareColumn(colCompareState?.column || [])}
        use:hoverTooltip={{text: 'Swap comparison order'}}><PropertyRelationship /></button
      >
    </div>
  </div>
  <div class="editor-container -ml-4 w-full" bind:this={editorContainer} />
</div>

<style lang="postcss">
  :global(.editor-container) {
    width: 100%;
  }
</style>
