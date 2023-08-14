import type {Notification} from '$lib/stores/notificationsStore';
import type {SvelteComponent} from 'svelte';
import type {SpanDetails} from './StringSpanDetails.svelte';
import StringSpanDetails from './StringSpanDetails.svelte';

export interface SpanClickInfo {
  details: () => SpanDetails;
  findSimilar: ((embedding: string, text: string) => unknown) | null;
  embeddings: string[];
  addConceptLabel: (
    conceptName: string,
    conceptNamespace: string,
    text: string,
    label: boolean
  ) => void;
  addNotification: (notification: Notification) => void;
  disabled: boolean;
}

export function spanClick(element: HTMLSpanElement, clickInfo: SpanClickInfo) {
  let spanDetailsComponent: SvelteComponent | undefined;
  let curClickInfo = clickInfo;
  element.addEventListener('click', e => showClickDetails(e));
  function showClickDetails(e: MouseEvent) {
    if (curClickInfo.disabled) {
      return;
    }
    spanDetailsComponent = new StringSpanDetails({
      props: {
        details: curClickInfo.details(),
        clickPosition: {x: e.clientX, y: e.clientY},
        embeddings: curClickInfo.embeddings,
        addConceptLabel: curClickInfo.addConceptLabel,
        addNotification: curClickInfo.addNotification,
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
