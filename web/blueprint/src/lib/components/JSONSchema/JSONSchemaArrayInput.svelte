<script lang="ts">
  /* eslint-disable @typescript-eslint/no-explicit-any */
  import type {Draft, JSONError} from 'json-schema-library';
  import type {SvelteComponent} from 'svelte';
  import JsonSchemaInput from './JSONSchemaInput.svelte';

  export let path: string;
  export let value: any[] = [];
  export let rootValue: any;
  export let schema: Draft;
  export let validationErrors: JSONError[] = [];
  export let customComponents: Record<string, typeof SvelteComponent>;

  // Get the schema for the array
  $: arrayProperty = schema.getSchema(path, value);

  // Create a template value that can be pushed into the array
  $: templateValue = schema.getTemplate(undefined, schema.getSchema(path + '/0', value));
</script>

<div class="bx--form-item flex flex-col">
  <span class="bx--label">{arrayProperty.title}</span>

  {#each value || [] as _, i}
    <div class="mb-4 flex w-full flex-row">
      <div class="w-8 shrink-0 text-lg">{i + 1}</div>
      <div class="flex w-full grow flex-col">
        <JsonSchemaInput
          path={path + '/' + i}
          {schema}
          {rootValue}
          bind:value={value[i]}
          {validationErrors}
          {customComponents}
          required
        />
        <button
          class="bg-slate-600 p-2 text-white hover:bg-slate-400"
          on:click={() => {
            value.splice(i, 1);
            value = value;
          }}>remove</button
        >
      </div>
    </div>
  {/each}
  <div>
    <button
      class="bg-slate-600 p-2 text-white hover:bg-slate-400"
      class:ml-8={value?.length > 0}
      on:click={() => {
        value = [...(value || []), templateValue];
      }}>+ add</button
    >
  </div>
</div>
