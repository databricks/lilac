import type {SvelteComponent} from 'svelte';
import type {SpanDetails} from './StringSpanDetails.svelte';
import StringSpanDetails from './StringSpanDetails.svelte';

export interface SpanClickInfo {
  details: () => SpanDetails;
  findSimilar: (embedding: string, text: string) => unknown;
  computedEmbeddings: string[];
  addConceptLabel: (
    conceptName: string,
    conceptNamespace: string,
    text: string,
    label: boolean
  ) => void;
}

export function spanClick(element: HTMLSpanElement, clickInfo: SpanClickInfo) {
  // Span clicks do nothing when there are no computed embeddings.
  if (clickInfo.computedEmbeddings.length === 0) {
    return;
  }
  let spanDetailsComponent: SvelteComponent | undefined;
  let curClickInfo = clickInfo;
  element.addEventListener('click', e => showClickDetails(e));
  function showClickDetails(e: MouseEvent) {
    spanDetailsComponent = new StringSpanDetails({
      props: {
        details: curClickInfo.details(),
        clickPosition: {x: e.clientX, y: e.clientY},
        computedEmbeddings: curClickInfo.computedEmbeddings,
        addConceptLabel: curClickInfo.addConceptLabel,
        findSimilar: curClickInfo.findSimilar
      },
      target: document.body
    });
    spanDetailsComponent.$on('close', destroyClickInfo);
    spanDetailsComponent.$on('click', destroyClickInfo);
  }

  function destroyClickInfo() {
    spanDetailsComponent?.$destroy();
    spanDetailsComponent = undefined;
  }

  return {
    update(clickInfo: SpanClickInfo) {
      curClickInfo = clickInfo;

      spanDetailsComponent?.$set({
        details: curClickInfo.details()
      });
    },
    destroy() {
      destroyClickInfo();
    }
  };
}
