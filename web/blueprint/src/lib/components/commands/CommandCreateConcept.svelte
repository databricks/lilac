<script lang="ts">
  import {createConceptMutation, editConceptMutation} from '$lib/queries/conceptQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {ConceptsService} from '$lilac';
  import {
    Button,
    ComposedModal,
    InlineLoading,
    ModalBody,
    ModalFooter,
    ModalHeader,
    TextInput
  } from 'carbon-components-svelte';
  import {Close} from 'carbon-icons-svelte';
  import {createEventDispatcher} from 'svelte';
  import type {CreateConceptCommand} from './Commands.svelte';

  export let command: CreateConceptCommand;

  const authInfo = queryAuthInfo();
  $: authEnabled = $authInfo.data?.auth_enabled;
  $: userId = $authInfo.data?.user?.id;

  $: defaultNamespace = (authEnabled ? userId : null) || 'local';

  $: namespace = command.namespace || defaultNamespace;
  let name = command.conceptName || '';
  let conceptDescription: string | undefined;
  let conceptDescLoading = false;

  const conceptCreate = createConceptMutation();
  const conceptEdit = editConceptMutation();

  const dispatch = createEventDispatcher();

  let positiveExamples: string[] = [''];

  function submit() {
    $conceptCreate.mutate([{namespace, name, type: 'text', description: conceptDescription}], {
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

  async function generateExamples() {
    if (!conceptDescription) return;
    conceptDescLoading = true;
    const examples = await ConceptsService.generateExamples(conceptDescription);
    conceptDescLoading = false;
    if (positiveExamples.at(-1) === '') {
      positiveExamples.pop();
    }
    positiveExamples.push(...examples);
    positiveExamples = positiveExamples;
  }

  function close() {
    dispatch('close');
  }
</script>

<ComposedModal open on:submit={submit} on:close={close} size="lg">
  <ModalHeader title="New Concept" />
  <ModalBody hasForm>
    <div class="flex flex-row gap-x-12">
      {#if authEnabled}
        <!--
          When authentication is enabled, the namespace is the user id so we don't show it
          to the user.
        -->
        <TextInput labelText="namespace" disabled />
      {:else}
        <TextInput labelText="namespace" bind:value={namespace} />
      {/if}
      <TextInput labelText="name" bind:value={name} required />
    </div>
    {#if authEnabled}
      <div class="mb-8 text-xs text-neutral-700">
        This concept will be created under your namespace, so only will be visible to you.
      </div>
    {/if}
    <div class="my-4 flex gap-x-2">
      <TextInput
        labelText="Concept description"
        helperText="This will be used by an LLM to generate example sentences."
        placeholder="Enter the concept description..."
        bind:value={conceptDescription}
      />
      <div class="pt-5">
        <Button on:click={generateExamples} disabled={!conceptDescription || conceptDescLoading}>
          Generate
          <span class="ml-2" class:invisible={!conceptDescLoading}><InlineLoading /></span>
        </Button>
      </div>
    </div>
    <div class="mb-2 mt-8">Add positive examples</div>
    <div>
      <div class="flex flex-col">
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
                iconDescription="Remove example"
                tooltipPosition="top"
                tooltipAlignment="end"
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
