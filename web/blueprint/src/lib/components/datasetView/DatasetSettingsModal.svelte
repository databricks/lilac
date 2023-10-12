<script lang="ts">
  import {goto} from '$app/navigation';
  import {deleteDatasetMutation, updateDatasetSettingsMutation} from '$lib/queries/datasetQueries';
  import {datasetIdentifier} from '$lib/utils';
  import type {DatasetSettings} from '$lilac';
  import {
    ComposedModal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    TextInput
  } from 'carbon-components-svelte';
  import {TrashCan} from 'carbon-icons-svelte';
  import CommandSelectList from '../commands/selectors/CommandSelectList.svelte';
  import DatasetSettingsFields from './DatasetSettingsFields.svelte';

  export let namespace: string;
  export let name: string;

  export let open = false;

  const updateSettings = updateDatasetSettingsMutation();

  $: identifier = datasetIdentifier(namespace, name);

  let settingsPage: 'fields' | 'administration' = 'fields';

  let newSettings: DatasetSettings | undefined = undefined;
  // TODO: bind settings to newSettings
  function submit() {
    if (newSettings == null) return;
    $updateSettings.mutate([namespace, name, newSettings], {
      onSuccess: () => {
        open = false;
      }
    });
  }

  let deleteDatasetInputName = '';
  const deleteDataset = deleteDatasetMutation();
</script>

<ComposedModal {open} on:submit={submit} on:close={() => (open = false)}>
  <ModalHeader label="Changes" title="Dataset settings" />
  <ModalBody hasForm>
    <div class="flex flex-row">
      <div class="-ml-4 mr-4 w-96 grow-0">
        <CommandSelectList
          items={[
            {
              title: 'Fields',
              value: 'fields'
            },
            {title: 'Administration', value: 'administration'}
          ]}
          item={settingsPage}
          on:select={e => (settingsPage = e.detail)}
        />
      </div>
      <div class="flex w-full flex-col gap-y-6 rounded border border-gray-300 bg-white p-4">
        {#if settingsPage === 'fields'}
          <DatasetSettingsFields {namespace} datasetName={name} bind:settings={newSettings} />
        {:else if settingsPage === 'administration'}
          <div class="flex flex-col gap-y-6">
            <section class="flex flex-col gap-y-1">
              <div class="text-lg text-gray-700">Delete this dataset</div>
              <div class="mb-4 text-sm text-gray-500">
                <p class="mb-2">This action cannot be undone.</p>
                <p>
                  This will permanently delete the
                  <span class="font-bold">{identifier}</span> dataset and all its files. Please type
                  <span class="font-bold">{identifier}</span> to confirm.
                </p>
              </div>
              <TextInput
                bind:value={deleteDatasetInputName}
                invalid={deleteDatasetInputName != identifier}
              />
              <button
                class="mt-2 flex cursor-pointer flex-row justify-between p-4 text-left outline-red-400 hover:bg-gray-200"
                class:cursor-not-allowed={deleteDatasetInputName != identifier}
                class:outline={deleteDatasetInputName == identifier}
                class:opacity-50={deleteDatasetInputName != identifier}
                disabled={deleteDatasetInputName != identifier}
                on:click={() =>
                  $deleteDataset.mutate([namespace, name], {onSuccess: () => goto('/')})}
              >
                I understand, delete this dataset
                <TrashCan />
              </button>
            </section>
          </div>
        {/if}
      </div>
    </div></ModalBody
  >
  <ModalFooter
    danger={settingsPage === 'administration'}
    primaryButtonText="Save"
    secondaryButtonText="Cancel"
    on:click:button--secondary={() => (open = false)}
    primaryButtonDisabled={settingsPage === 'administration'}
  />
</ComposedModal>
