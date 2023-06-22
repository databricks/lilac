import type {SvelteComponent} from 'svelte';
import HoverTooltip from './HoverTooltip.svelte';

interface HoverTooltipOptions {
  // The text to show upon hover.
  text?: string;
  // The component to show upon hover. This can be defined if the body of the hover is complicated
  // HTML.
  component?: typeof SvelteComponent;
  // The props to pass to the body component.
  props?: Record<string, unknown>;
}

export function hoverTooltip(
  element: HTMLElement,
  {text: tooltipText, component: tooltipBodyComponent, props: tooltipBodyProps}: HoverTooltipOptions
) {
  let tooltipComponent: SvelteComponent | undefined;
  let curTooltipText = tooltipText;
  let curTooltipBodyComponent = tooltipBodyComponent;
  let curTooltipBodyProps = tooltipBodyProps;
  function mouseOver() {
    if (tooltipComponent != null) return;
    const boundingRect = element.getBoundingClientRect();

    tooltipComponent = new HoverTooltip({
      props: {
        tooltipText: curTooltipText,
        tooltipBodyComponent: curTooltipBodyComponent,
        tooltipBodyProps: curTooltipBodyProps,
        x: boundingRect.left + boundingRect.width / 2,
        y: boundingRect.bottom
      },
      target: document.body
    });
  }

  function mouseLeave() {
    tooltipComponent?.$destroy();
    tooltipComponent = undefined;
  }

  element.addEventListener('mouseover', mouseOver);
  element.addEventListener('mouseleave', mouseLeave);

  return {
    update({
      text: tooltipText,
      component: tooltipBodyComponent,
      props: tooltipBodyProps
    }: HoverTooltipOptions) {
      curTooltipText = tooltipText;
      curTooltipBodyComponent = tooltipBodyComponent;
      curTooltipBodyProps = tooltipBodyProps;
      tooltipComponent?.$set({tooltipText});
    },
    destroy() {
      mouseLeave();
      element.removeEventListener('mouseover', mouseOver);
      element.removeEventListener('mouseleave', mouseLeave);
    }
  };
}
