<script lang="ts">
  import {
    CONTEXT_TEMPLATE_VAR,
    QUERY_TEMPLATE_VAR,
    getRagViewContext
  } from '$lib/stores/ragViewStore';
  import type {RagRetrievalResultItem} from '$lilac';
  import {
    ComposedModal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    TextArea
  } from 'carbon-components-svelte';
  import {createEventDispatcher} from 'svelte';

  // The question while the user is typing. When the user presses the search button, the rag store
  // updated and the prompt is updated.
  export let questionInputText: string;
  // Results from the retrieval component.
  export let retrievalResults: RagRetrievalResultItem[] | undefined;

  const ragViewStore = getRagViewContext();
  const dispatch = createEventDispatcher();

  let promptTemplateModalOpen = false;
  let promptTemplateInputText = '';
  $: {
    if ($ragViewStore.promptTemplate != null) {
      promptTemplateInputText = $ragViewStore.promptTemplate;
    }
  }

  function getPrompt(question: string, contextStr: string) {
    return promptTemplateInputText
      .replace(QUERY_TEMPLATE_VAR, question)
      .replace(CONTEXT_TEMPLATE_VAR, contextStr);
  }

  $: contextStr =
    retrievalResults == null ? CONTEXT_TEMPLATE_VAR : retrievalResults.map(r => r.text).join('\n');
  // The pending prompt. This is always defined, and can contain the template variables. Used for
  // displaying the prompt while the user is typing.
  $: pendingPrompt = getPrompt(questionInputText, contextStr);

  // The final prompt. This is only defined when there are valid retrieval results.
  $: {
    if (retrievalResults != null && $ragViewStore.query != null) {
      dispatch('promptTemplate', promptTemplateInputText);
    }
  }

  function promptInputChanged(e: Event) {
    promptTemplateInputText = (e.target as HTMLInputElement).value;
  }
  function submitPromptTemplate() {
    promptTemplateModalOpen = false;
  }
</script>

<div class="flex h-full w-full flex-col overflow-y-scroll">
  <div class="h-96 w-full overflow-y-scroll whitespace-break-spaces font-mono leading-6">
    {pendingPrompt}
  </div>
</div>
<ComposedModal
  open={promptTemplateModalOpen}
  on:submit={submitPromptTemplate}
  on:close={() => (promptTemplateModalOpen = false)}
>
  <ModalHeader title={'Edit prompt template'} />
  <ModalBody hasForm>
    <TextArea
      value={promptTemplateInputText || undefined}
      on:input={promptInputChanged}
      placeholder="Enter a prompt template..."
      rows={12}
      class="mb-2 w-full"
    /></ModalBody
  >
  <ModalFooter
    primaryButtonText={'Save'}
    secondaryButtonText="Close"
    primaryButtonDisabled={false}
    on:click:button--secondary={() => {
      close();
      promptTemplateModalOpen = false;
    }}
  />
</ComposedModal>
