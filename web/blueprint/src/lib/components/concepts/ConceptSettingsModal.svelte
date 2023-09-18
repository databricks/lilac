<script lang="ts">
  import {goto} from '$app/navigation';
  import {
    deleteConceptMutation,
    editConceptMetadataMutation,
    queryConcepts
  } from '$lib/queries/conceptQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {conceptDisplayName} from '$lib/view_utils';
  import {
    Checkbox,
    ComposedModal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    SkeletonText,
    TextArea,
    TextInput
  } from 'carbon-components-svelte';
  import {TrashCan, View, ViewOff} from 'carbon-icons-svelte';
  import CommandSelectList from '../commands/selectors/CommandSelectList.svelte';

  export let namespace: string;
  export let conceptName: string;

  const concepts = queryConcepts();

  $: conceptInfo = $concepts.data?.find(c => c.namespace === namespace && c.name === conceptName);
  $: metadata = conceptInfo?.metadata || {};

  const authInfo = queryAuthInfo();
  $: displayName = conceptDisplayName(namespace, conceptName, $authInfo.data);

  export let open = false;

  let settingsPage: 'general' | 'administration' = 'general';

  const editConceptMetadata = editConceptMetadataMutation();

  function submit() {
    open = false;

    if (metadata != null) {
      $editConceptMetadata.mutate([namespace, conceptName, metadata]);
    }
  }

  function descriptionChange(e: Event) {
    const description = (e.target as HTMLTextAreaElement).value;
    metadata = {...metadata, description};
  }

  let deleteConceptInputName = '';
  const deleteConcept = deleteConceptMutation();
</script>

<ComposedModal {open} on:submit={submit} on:close={() => (open = false)}>
  <ModalHeader label={conceptName} title="Concept settings" />
  <ModalBody hasForm>
    <div class="flex flex-row">
      <div class="-ml-4 mr-4 w-96 grow-0 p-1">
        <CommandSelectList
          items={[
            {
              title: 'General',
              value: 'general'
            },
            {title: 'Administration', value: 'administration'}
          ]}
          item={settingsPage}
          on:select={e => (settingsPage = e.detail)}
        />
      </div>
      <div class="flex w-full flex-col gap-y-6 rounded border border-gray-300 bg-white p-4">
        {#if settingsPage === 'general'}
          {#if $concepts.isFetching}
            <SkeletonText />
          {:else}
            <div class="flex flex-col gap-y-6">
              <section class="flex flex-col gap-y-1">
                <div class="text-base">Description</div>

                <TextArea
                  value={metadata.description || undefined}
                  on:input={descriptionChange}
                  cols={50}
                  placeholder="Enter a description..."
                  rows={3}
                  class="mb-2"
                />
              </section>
              <section class="flex flex-col gap-y-1">
                <div class="text-base">Visibility</div>

                <div class="flex flex-row items-center">
                  <Checkbox
                    labelText="Publicly visible"
                    checked={metadata.is_public}
                    on:check={e => (metadata = {...metadata, is_public: e.detail})}
                  />
                  {#if metadata.is_public}
                    <View />
                  {:else}
                    <ViewOff />
                  {/if}
                </div>
                <div class="text-xs font-light">
                  Setting the concept to publicly visible will allow any user with access to this
                  Lilac instance to view this concept.
                </div>
              </section>
            </div>
          {/if}
        {:else if settingsPage === 'administration'}
          <div class="flex flex-col gap-y-6">
            <section class="flex flex-col gap-y-1">
              <section class="flex flex-col gap-y-1">
                <div class="text-lg text-gray-700">Delete this concept</div>
                <div class="mb-4 text-sm text-gray-500">
                  <p class="mb-2">This action cannot be undone.</p>
                  <p>
                    This will permanently delete the
                    <span class="font-bold">{displayName}</span> dataset and all its files. Please
                    type
                    <span class="font-bold">{displayName}</span> to confirm.
                  </p>
                </div>
                <TextInput
                  bind:value={deleteConceptInputName}
                  invalid={deleteConceptInputName != displayName}
                />
                <button
                  class="mt-2 flex cursor-pointer flex-row justify-between p-4 text-left outline-red-400 hover:bg-gray-200"
                  class:cursor-not-allowed={deleteConceptInputName != displayName}
                  class:outline={deleteConceptInputName == displayName}
                  class:opacity-50={deleteConceptInputName != displayName}
                  disabled={deleteConceptInputName != displayName}
                  on:click={() =>
                    $deleteConcept.mutate([namespace, conceptName], {onSuccess: () => goto('/')})}
                >
                  I understand, delete this concept
                  <TrashCan />
                </button>
              </section>
            </section>
          </div>
        {/if}
      </div>
    </div>
  </ModalBody>
  <ModalFooter
    danger={settingsPage === 'administration'}
    primaryButtonText="Save"
    secondaryButtonText="Cancel"
    on:click:button--secondary={close}
    primaryButtonDisabled={settingsPage === 'administration'}
  />
</ComposedModal>
