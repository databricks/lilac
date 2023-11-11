import loader from '@monaco-editor/loader';
import type * as Monaco from 'monaco-editor/esm/vs/editor/editor.api';

let monacoInstance: Promise<typeof Monaco>;

export async function getMonaco(): Promise<typeof Monaco> {
  if (monacoInstance != null) {
    return monacoInstance;
  }
  monacoInstance = import('monaco-editor').then(monacoEditor => {
    loader.config({monaco: monacoEditor.default});
    return loader.init();
  });
  return monacoInstance;
}
