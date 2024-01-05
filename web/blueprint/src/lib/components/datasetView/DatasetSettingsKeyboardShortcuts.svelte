<script lang="ts">
  import type {DatasetSettings} from '$lilac';
  import {Keyboard, Tag} from 'carbon-icons-svelte';
  import {hoverTooltip} from '../common/HoverTooltip';

  export let newSettings: DatasetSettings | null;
  export let labels: string[] | undefined;

  const INVALID_KEYCODES = ['ArrowLeft', 'ArrowRight', 'Delete', 'Backspace'];

  let activeSetLabelIndex: number | undefined = undefined;

  function onKeyDown(key: KeyboardEvent) {
    if (activeSetLabelIndex == null || newSettings == null || labels == null) {
      return;
    }
    if (INVALID_KEYCODES.includes(key.code)) {
      return;
    }
    if (newSettings.ui == null) {
      newSettings.ui = {};
    }
    if (newSettings.ui.label_keyboard_shortcuts == null) {
      newSettings.ui.label_keyboard_shortcuts = {};
    }
    newSettings.ui.label_keyboard_shortcuts[labels[activeSetLabelIndex]] = key.code;
    activeSetLabelIndex = undefined;
  }
</script>

<div class="mb-8 flex flex-col gap-y-4">
  <section class="flex flex-col gap-y-1">
    <div class="text-lg text-gray-700">Label shortcuts</div>
    <div class="text-sm text-gray-500">
      <p>
        Keyboard shortcuts for toggling a label on a row. Key codes are standard browser <a
          href="https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent/code">key codes</a
        >.
      </p>
      <br />
      <p>
        To edit a key code, click the keyboard icon, and press the corresponding key on the keyboard
        to set the shortcut.
      </p>
    </div>

    <table class="mt-4">
      {#each labels || [] as label, i}
        <tr class="h-12 items-center gap-x-8 gap-y-1">
          <td class="w-36">
            <div
              class="flex w-fit flex-row items-center gap-x-2 rounded-lg border border-gray-300 bg-transparent bg-white p-1"
            >
              <Tag />
              {label}
            </div>
          </td>
          <td class="flex h-8 w-16 flex-row items-center gap-x-1">
            <button
              class="flex h-full w-16 items-center rounded border border-gray-300 p-1"
              class:bg-blue-300={i === activeSetLabelIndex}
              use:hoverTooltip={{text: 'Set keyboard shortcut'}}
              on:click={() => {
                activeSetLabelIndex = i;
              }}
              ><Keyboard />
            </button>
            <input
              disabled
              type="text"
              class="h-8 w-16 rounded border border-neutral-200 px-2 text-center"
              value={newSettings?.ui?.label_keyboard_shortcuts?.[label] || ''}
            />
          </td>
        </tr>
      {/each}
    </table>
  </section>
</div>
<svelte:window on:keydown={onKeyDown} />
