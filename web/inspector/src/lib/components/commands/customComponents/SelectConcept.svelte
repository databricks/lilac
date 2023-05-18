<script lang="ts">
  import {queryConcepts} from '$lib/queries/conceptQueries';
  import {Select, SelectItem, SelectItemGroup} from 'carbon-components-svelte';

  export let rootValue: {namespace: string; concept_name: string};
  export let invalid: boolean;
  export let invalidText: string;
  export let value: string;

  const concepts = queryConcepts();

  // Unique namespaces
  $: namespaces = $concepts.isSuccess ? [...new Set($concepts.data.map(c => c.namespace))] : [];

  // Concepts grouped by namespace
  $: conceptGroups = $concepts.isSuccess
    ? namespaces.map(namespace => ({
        namespace,
        concepts: $concepts.data?.filter(c => c.namespace === namespace) || []
      }))
    : [];

  $: {
    if (!value && $concepts.isSuccess) {
      rootValue.namespace = $concepts.data[0].namespace;
      value = $concepts.data[0].name;
    }
  }

  function onChange(ev: CustomEvent<string | number>) {
    const [namespace, conceptName] = ev.detail.toString().split('/');
    if (!namespace || !conceptName) return;
    rootValue.namespace = namespace;
    value = conceptName;
  }
</script>

<Select labelText="Concept *" on:update={onChange} {invalid} {invalidText}>
  {#if $concepts.isSuccess}
    {#each conceptGroups as group}
      <SelectItemGroup label={group.namespace}>
        {#each group.concepts as concept}
          <SelectItem value={`${group.namespace}/${concept.name}`} text={concept.name} />
        {/each}
      </SelectItemGroup>
    {/each}
  {/if}
</Select>
