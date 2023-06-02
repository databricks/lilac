<script lang="ts">
  import {querySelectRowsSchema} from '$lib/queries/datasetQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext, getSelectRowsOptions} from '$lib/stores/datasetViewStore';
  import {
    childFields,
    getField,
    pathIsEqual,
    type BinaryFilter,
    type BinaryOp,
    type LilacField,
    type ListFilter,
    type ListOp,
    type UnaryFilter,
    type UnaryOp
  } from '$lilac';
  import {
    Checkbox,
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
  const datasetStore = getDatasetContext();

  const dispatch = createEventDispatcher();

  $: selectRowsSchema = $datasetStore?.schema
    ? querySelectRowsSchema(
        command.namespace,
        command.datasetName,
        getSelectRowsOptions($datasetViewStore)
      )
    : undefined;

  // Create list of fields, and include current count of filters
  $: fields =
    $selectRowsSchema?.isSuccess && $datasetStore?.schema
      ? childFields($datasetStore?.schema).map(f => {
          const filters = stagedFilters.filter(filter => pathIsEqual(filter.path, f.path));
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

  $: defaultField = $selectRowsSchema?.isSuccess
    ? getField($selectRowsSchema.data.schema, command.path)
    : undefined;

  // Copy filters from query options
  let stagedFilters: (UnaryFilter | ListFilter | BinaryFilter)[] = [];
  onMount(() => {
    stagedFilters = structuredClone($datasetViewStore.queryOptions.filters || []);
  });

  $: currentFieldFilters = stagedFilters.filter(f =>
    pathIsEqual(f.path, selectedField?.alias || selectedField?.path)
  );

  // Ensure that exists ops have null value
  $: {
    for (const filter of stagedFilters) {
      if (filter.op === 'exists') {
        filter.value = null;
      }
    }
  }

  let selectedField: LilacField | undefined = undefined;

  $: if (!selectedField && defaultField) {
    selectedField = defaultField;
  }

  const operations: [BinaryOp | UnaryOp | ListOp, string][] = [
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
        <CommandSelectList
          items={fields}
          item={selectedField}
          on:select={ev => (selectedField = ev.detail)}
        />
      </div>
      <div class="flex w-full flex-col gap-y-6">
        {#if selectedField}
          {@const fieldPath = selectedField.alias || selectedField.path}
          {#each currentFieldFilters as filter}
            <div class="flex items-center gap-x-2">
              <Select bind:selected={filter.op} labelText="Operation">
                {#each operations as op}
                  <SelectItem value={op[0]} text={op[1]} />
                {/each}
              </Select>
              {#if filter.op === 'exists'}
                <!-- Dont show any seconday input -->
              {:else if filter.op === 'in'}
                <span>In operator not yet implemented</span>
              {:else if typeof filter.value === 'boolean'}
                <Checkbox />
              {:else if typeof filter.value === 'function'}
                <span>Blob filter not yet implemented</span>
              {:else}
                <TextInput labelText="Value" bind:value={filter.value} />
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
