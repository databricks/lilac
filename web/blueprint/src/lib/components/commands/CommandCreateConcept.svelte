<script lang="ts">
  import {createConceptMutation, editConceptMutation} from '$lib/queries/conceptQueries';
  import {
    Button,
    ComposedModal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    TextInput
  } from 'carbon-components-svelte';
  import {Close} from 'carbon-icons-svelte';
  import {createEventDispatcher} from 'svelte';
  import type {CreateConceptCommand} from './Commands.svelte';

  export let command: CreateConceptCommand;
  let namespace = command.namespace || 'local';
  let name = command.conceptName || '';

  const conceptCreate = createConceptMutation();
  const conceptEdit = editConceptMutation();

  const dispatch = createEventDispatcher();

  let positiveExamples: string[] = [''];

  function submit() {
    $conceptCreate.mutate([{namespace, name, type: 'text'}], {
      onSuccess: () => {
        $conceptEdit.mutate(
          [
            namespace,
            name,
            {
              insert: positiveExamples.filter(text => text != '').map(text => ({text, label: true}))
            }
          ],
          {
            onSuccess: () => {
              dispatch('create', {namespace, name});
              close();
            }
          }
        );
      }
    });
  }

  function close() {
    dispatch('close');
  }
</script>

<ComposedModal open on:submit={submit} on:close={close}>
  <ModalHeader title="New Concept" />
  <ModalBody hasForm>
    <div class="flex flex-row gap-x-12">
      <TextInput labelText="namespace" bind:value={namespace} />
      <TextInput labelText="name" bind:value={name} required />
    </div>
    <div class="mb-2 mt-8">Add positive examples</div>
    <div>
      <div class="flex flex-col overflow-hidden">
        {#each positiveExamples || [] as _, i}
          <div class="mb-4 flex flex-row">
            <div class="w-8 shrink-0 text-lg">{i + 1}</div>
            <div class="grow">
              <TextInput bind:value={positiveExamples[i]} />
            </div>
            <div>
              <Button
                kind="ghost"
                icon={Close}
                expressive={true}
                on:click={() => {
                  positiveExamples.splice(i, 1);
                  positiveExamples = positiveExamples;
                }}
              />
            </div>
          </div>
        {/each}
      </div>
      <div>
        <button
          class="bg-slate-600 p-2 text-white hover:bg-slate-400"
          class:ml-8={positiveExamples?.length > 0}
          on:click={() => {
            positiveExamples = [...(positiveExamples || []), ''];
          }}>+ add</button
        >
      </div>
    </div>
  </ModalBody>
  <ModalFooter
    primaryButtonText="Create"
    secondaryButtonText="Cancel"
    primaryButtonDisabled={namespace.length == 0 || name.length == 0}
    on:click:button--secondary={close}
  />
</ComposedModal>
