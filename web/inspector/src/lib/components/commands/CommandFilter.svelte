<script lang="ts">
  import {querySelectRowsSchema} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {
    getField,
    listFields,
    pathIsEqual,
    type BinaryOp,
    type Filter,
    type LilacSchemaField,
    type Path,
    type UnaryOp
  } from '$lilac';
  import {
    ComposedModal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    Select,
    SelectItem,
    TextInput
  } from 'carbon-components-svelte';
  import type {TagProps} from 'carbon-components-svelte/types/Tag/Tag.svelte';
  import CloseOutline from 'carbon-icons-svelte/lib/CloseOutline.svelte';
  import {createEventDispatcher, onMount} from 'svelte';
  import type {EditFilterCommand} from './Commands.svelte';
  import CommandSelectList from './selectors/CommandSelectList.svelte';

  export let command: EditFilterCommand;

  const datasetViewStore = getDatasetViewContext();
  const dispatch = createEventDispatcher();

  $: schema = querySelectRowsSchema(
    command.namespace,
    command.datasetName,
    $datasetViewStore.queryOptions
  );

  // Create list of fields, and include current count of filters
  $: fields = $schema.isSuccess
    ? listFields($schema.data).map(f => {
        const filters = stagedFilters.filter(filter => pathIsEqual(filter.path as Path, f.path));
        return {
          title: f.path.join('.'),
          value: f,
          tag:
            filters.length > 0
              ? {value: filters.length.toString(), type: 'blue' as TagProps['type']}
              : undefined
        };
      })
    : [];

  $: defaultField = $schema.isSuccess ? getField($schema.data, command.path) : undefined;

  // Copy filters from query options
  let stagedFilters: Filter[] = [];
  onMount(() => {
    stagedFilters = structuredClone($datasetViewStore.queryOptions.filters || []);
  });

  $: currentFieldFilters = stagedFilters.filter(f =>
    pathIsEqual(f.path as Path, selectedField?.path)
  );

  let selectedField: LilacSchemaField | undefined = undefined;

  const operations: [BinaryOp | UnaryOp, string][] = [
    ['equals', 'equals (=)'],
    ['not_equal', 'not equal (!=)'],
    ['greater', 'greater than (>)'],
    ['greater_equal', 'greater or equal (>=)'],
    ['less', 'less than (<)'],
    ['less_equal', 'less or equal (<=)'],
    ['in', 'in'],
    ['exists', 'exists']
  ];

  function close() {
    dispatch('close');
  }

  function submit() {
    $datasetViewStore.queryOptions.filters = stagedFilters;
    close();
  }
</script>

<ComposedModal open on:submit={submit} on:close={close}>
  <ModalHeader label="Filters" title="Edit Filters" />
  <ModalBody hasForm>
    <div class="flex flex-row">
      <div class="-ml-4 mr-4 w-80 grow-0">
        <CommandSelectList items={fields} bind:item={selectedField} defaultItem={defaultField} />
      </div>
      <div class="flex w-full flex-col gap-y-6">
        {#if selectedField}
          {@const fieldPath = selectedField.path}
          {#each currentFieldFilters as filter}
            <div class="flex items-center gap-x-2">
              <Select bind:selected={filter.op} labelText="Operation">
                {#each operations as op}
                  <SelectItem value={op[0]} text={op[1]} />
                {/each}
              </Select>
              {#if typeof filter.value === 'string'}
                <TextInput labelText="Value" bind:value={filter.value} />
              {:else}
                <TextInput labelText="Value" value="Unsuported type" disabled />
              {/if}
              <button
                class="mt-5"
                on:click={() => {
                  stagedFilters = stagedFilters.filter(f => f != filter);
                }}><CloseOutline size={20} /></button
              >
            </div>
          {/each}
          <div>
            <button
              class="uppercase text-blue-500 hover:underline"
              on:click={() =>
                (stagedFilters = [
                  ...stagedFilters,
                  {
                    path: fieldPath,
                    op: 'equals',
                    value: ''
                  }
                ])}>{currentFieldFilters.length > 0 ? 'and' : 'add'}</button
            >
          </div>
        {/if}
      </div>
    </div>
  </ModalBody>
  <ModalFooter
    primaryButtonText="Save"
    secondaryButtonText="Cancel"
    primaryButtonDisabled={false}
    on:click:button--secondary={close}
  />
</ComposedModal>
