import type {DatasetState} from '$lib/stores/datasetStore';
import type {DatasetViewStore} from '$lib/stores/datasetViewStore';
import type {SignalInfoWithTypedSchema} from '$lilac';
import type {SvelteComponent} from 'svelte';
import type {Readable} from 'svelte/store';
import type {SpanDetails} from './StringSpanDetails.svelte';
import StringSpanDetails from './StringSpanDetails.svelte';

export interface SpanClickInfo {
  details: () => SpanDetails;
  datasetViewStore: DatasetViewStore;
  datasetStore: Readable<DatasetState>;
  embeddings: SignalInfoWithTypedSchema[];
  addConceptLabel: (
    conceptName: string,
    conceptNamespace: string,
    text: string,
    label: boolean
  ) => void;
}

export function spanClick(element: HTMLSpanElement, clickInfo: SpanClickInfo) {
  let spanDetailsComponent: SvelteComponent | undefined;
  let curClickInfo = clickInfo;
  element.addEventListener('click', e => showClickDetails(e));
  function showClickDetails(e: MouseEvent) {
    spanDetailsComponent = new StringSpanDetails({
      props: {
        details: curClickInfo.details(),
        clickPosition: {x: e.clientX, y: e.clientY},
        datasetViewStore: curClickInfo.datasetViewStore,
        datasetStore: curClickInfo.datasetStore,
        embeddings: curClickInfo.embeddings,
        addConceptLabel: curClickInfo.addConceptLabel
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
