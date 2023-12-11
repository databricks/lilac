import loader from '@monaco-editor/loader';
import type * as Monaco from 'monaco-editor/esm/vs/editor/editor.api';

export const MAX_MONACO_HEIGHT_COLLAPSED = 360;
export const MAX_MONACO_HEIGHT_EXPANDED = 720;
let monacoInstance: Promise<typeof Monaco>;

export const MONACO_OPTIONS: Monaco.editor.IStandaloneEditorConstructionOptions = {
  // Inconsolata variable comes from the @fontsource-variable/inconsolata NPM package so we don't
  // hit google fonts on every page load.
  fontFamily: 'inconsolata variable',
  fontSize: 14,
  readOnly: true,
  lineNumbers: 'off',
  renderFinalNewline: 'dimmed',
  lineDecorationsWidth: 0,
  folding: false,
  roundedSelection: true,
  domReadOnly: true,
  scrollBeyondLastLine: false,
  wordWrap: 'on',
  wrappingStrategy: 'advanced',
  readOnlyMessage: {value: ''},
  scrollbar: {
    verticalScrollbarSize: 8,
    alwaysConsumeMouseWheel: false
  },
  // Allows the hovers to be hoisted out of the editor and not get cut off.
  fixedOverflowWidgets: true,
  language: 'text/plain',
  automaticLayout: true
};

export async function getMonaco(): Promise<typeof Monaco> {
  if (monacoInstance != null) {
    return monacoInstance;
  }
  monacoInstance = import('monaco-editor').then(async monacoEditor => {
    loader.config({monaco: monacoEditor.default});
    return loader.init();
  });
  return monacoInstance;
}
