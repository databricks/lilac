import loader from '@monaco-editor/loader';
import type * as Monaco from 'monaco-editor/esm/vs/editor/editor.api';

export const MONACO_LANGUAGE = 'lilac_text';
export const MAX_MONACO_HEIGHT_COLLAPSED = 360;
export const MAX_MONACO_HEIGHT_EXPANDED = 720;
let monacoInstance: Promise<typeof Monaco>;

export const MONACO_OPTIONS: Monaco.editor.IStandaloneEditorConstructionOptions = {
  fontFamily: 'Inconsolata',
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
  language: MONACO_LANGUAGE,
  automaticLayout: true
};

export async function getMonaco(): Promise<typeof Monaco> {
  if (monacoInstance != null) {
    return monacoInstance;
  }
  monacoInstance = import('monaco-editor').then(async monacoEditor => {
    loader.config({monaco: monacoEditor.default});
    const monaco = await loader.init();

    setupHovers(monaco);
    // This is required to make sure that the fonts are loaded before the editor measures its size.
    // If not set, hovers will be misaligned.
    document.fonts.ready.then(() => {
      monaco.editor.remeasureFonts();
    });

    return monaco;
  });
  return monacoInstance;
}

/**
 * Register the single global hover provider for all monaco instances with the lilac language.
 * @param monaco
 */
function setupHovers(monaco: typeof Monaco) {
  monaco.languages.register({id: MONACO_LANGUAGE});

  monaco.languages.registerHoverProvider(MONACO_LANGUAGE, {
    provideHover: function (model, position, token) {
      const callback = MONACO_HOVER_CALLBACKS.get(model.id);
      if (callback != null) {
        return callback(model, position, token);
      }
    }
  });
}

// Maps a model id to its hover callback.
const MONACO_HOVER_CALLBACKS = new Map<
  string,
  (
    model: Monaco.editor.ITextModel,
    position: Monaco.Position,
    token: Monaco.CancellationToken
  ) => Monaco.languages.ProviderResult<Monaco.languages.Hover>
>();

export function registerHoverProvider(
  model: Monaco.editor.ITextModel,
  callback: (
    model: Monaco.editor.ITextModel,
    position: Monaco.Position,
    token: Monaco.CancellationToken
  ) => Monaco.languages.ProviderResult<Monaco.languages.Hover>
) {
  MONACO_HOVER_CALLBACKS.set(model.id, callback);
}

export function removeHoverProvider(model: Monaco.editor.ITextModel) {
  MONACO_HOVER_CALLBACKS.delete(model.id);
}
