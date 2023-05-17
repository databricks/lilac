<script lang="ts">
  import {goto} from '$app/navigation';
  import {
    ComposedModal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    TextInput
  } from 'carbon-components-svelte';
  import {createEventDispatcher} from 'svelte';

  let namespace = 'local';
  let name = '';

  const dispatch = createEventDispatcher();

  function submit() {
    close();
    goto('/concepts/' + namespace + '/' + name);
  }

  function close() {
    dispatch('close');
  }
</script>

<ComposedModal open on:submit={submit} on:close={close}>
  <ModalHeader label="Concepts" title="New Concept" />
  <ModalBody hasForm>
    <div class="flex flex-col gap-y-4">
      <TextInput labelText="namespace" bind:value={namespace} />
      <TextInput labelText="name" bind:value={name} required />
    </div>
  </ModalBody>
  <ModalFooter
    primaryButtonText="Create"
    secondaryButtonText="Cancel"
    primaryButtonDisabled={namespace.length == 0 || name.length == 0}
    on:click:button--secondary={close}
  />
</ComposedModal>
