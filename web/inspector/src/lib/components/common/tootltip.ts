import type {SvelteComponent} from 'svelte';
import Tooltip from './TooltipFromAction.svelte';

export function tooltip(element: HTMLElement) {
  let title: string;
  let tooltipComponent: SvelteComponent | undefined;
  function mouseOver(event: MouseEvent) {
    // NOTE: remove the `title` attribute, to prevent showing the default browser tooltip
    // remember to set it back on `mouseleave`
    title = element.getAttribute('title') || '';
    if (!title.length) return;

    element.removeAttribute('title');

    tooltipComponent = new Tooltip({
      props: {
        title: title,
        x: event.pageX,
        y: event.pageY
      },
      target: document.body
    });
  }
  function mouseMove(event: MouseEvent) {
    tooltipComponent?.$set({
      x: event.pageX,
      y: event.pageY
    });
  }
  function mouseLeave() {
    tooltipComponent?.$destroy();
    element.setAttribute('title', title);
  }

  element.addEventListener('mouseover', mouseOver);
  element.addEventListener('mouseleave', mouseLeave);
  element.addEventListener('mousemove', mouseMove);

  return {
    destroy() {
      tooltipComponent?.$destroy();
      element.removeEventListener('mouseover', mouseOver);
      element.removeEventListener('mouseleave', mouseLeave);
      element.removeEventListener('mousemove', mouseMove);
    }
  };
}
