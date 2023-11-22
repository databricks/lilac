/**
 * Hoists an element out of the DOM and positions it absolutely where it was.
 */
export function hoist(element: HTMLElement) {
  const boundingRect = element.getBoundingClientRect();
  document.body.append(element);
  element.style.position = 'absolute';
  element.style.top = `${boundingRect.top}px`;
  element.style.left = `${boundingRect.left}px`;
}
