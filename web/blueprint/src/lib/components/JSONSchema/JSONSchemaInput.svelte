<script lang="ts">
  /* eslint-disable @typescript-eslint/no-explicit-any */
  import {NumberInput, Select, SelectItem, TextInput, Toggle} from 'carbon-components-svelte';
  import type {Draft, JSONError} from 'json-schema-library';
  import type {SvelteComponent} from 'svelte';
  import SvelteMarkdown from 'svelte-markdown';
  import JsonSchemaArrayInput from './JSONSchemaArrayInput.svelte';

  /** The json schema to use */
  export let schema: Draft;
  /** The path to the property in the schema */
  export let path = '';
  /** Whether the property is required */
  export let required = false;
  /** The value of the property */
  export let value: any;
  /** The root value of the schema */
  export let rootValue: any;
  /** List of property keys that are hidden */
  export let hiddenProperties: string[] = [];
  /** Whether to show the description */
  export let showDescription = true;
  /** List of validation errors */
  export let validationErrors: JSONError[] = [];
  /** Custom components to use for certain properties */
  export let customComponents: Record<string, typeof SvelteComponent>;

  $: property = schema.getSchema(path);
  $: propertyType = 'anyOf' in property ? property.anyOf[0].type : property.type;
  $: label = property.title ? `${property.title} ${required ? '*' : ''}` : '';

  // FInd the validation error for this property using some pointer magic
  $: validation = validationErrors.filter(
    err =>
      `${err?.data?.pointer}${err?.data?.key ? '/' + err?.data?.key : ''}`.replaceAll('#', '') ==
      path
  );

  // Convert a null value to undefined for the json schema to validate.
  $: {
    value = value === null ? undefined : value;
  }

  // Map common validation errors to user friendly messages
  let validationText = '';
  $: {
    if (validation.length == 0) validationText = '';
    else if (validation[0].code === 'min-length-one-error') {
      validationText = 'Value is required';
    } else if (validation[0].code === 'required-property-error') {
      validationText = 'Value is required';
    } else {
      validationText = validation[0].message;
    }
  }

  // Replace empty strings with undefined
  $: {
    if (value === '') value = undefined;
  }
</script>

{#if !hiddenProperties?.includes(path)}
  {#if propertyType === 'object'}
    {#if property.description && showDescription}
      <div class="description mb-4">
        <SvelteMarkdown source={property.description} />
      </div>
    {/if}
  {:else}
    <div class="label text-s mb-2 font-medium text-gray-700">{label}</div>
    {#if property.description && showDescription}
      <div class="bx--label pb-1 text-xs text-gray-500">
        {property.description}
      </div>
    {/if}
  {/if}
  {#if customComponents[path]}
    <svelte:component
      this={customComponents[path]}
      bind:value
      {rootValue}
      invalid={!!validation.length}
      invalidText={validationText}
    />
  {:else if propertyType == 'error'}
    <!-- Error -->
    <div class="text-red-600">{property.message}</div>
  {:else if property.enum}
    <Select bind:selected={value} name={path} labelText={label} hideLabel={true}>
      {#if !required}
        <SelectItem value={undefined} text={'None'} />
      {/if}
      {#each property.enum as item}
        <SelectItem value={item} />
      {/each}
    </Select>
  {:else if propertyType == 'string'}
    <!-- Text Input -->
    <TextInput
      bind:value
      name={path}
      invalid={!!validation.length}
      invalidText={validationText}
      labelText={label}
      hideLabel={true}
      placeholder={!required ? '(optional)' : ''}
    />
  {:else if propertyType == 'number' || propertyType == 'integer'}
    <!-- Number Input -->
    <NumberInput
      allowEmpty={!required}
      bind:value
      name={path}
      {label}
      hideLabel={true}
      invalid={!value && required}
    />
  {:else if propertyType == 'boolean'}
    <!-- Boolean Input -->
    <div>
      <Toggle
        labelA={'False'}
        labelB={'True'}
        labelText={label}
        hideLabel={true}
        bind:toggled={value}
      />
    </div>
  {:else if propertyType == 'array'}
    <!-- List of inputs -->
    <JsonSchemaArrayInput
      {path}
      bind:value
      {schema}
      {validationErrors}
      {customComponents}
      {rootValue}
    />
  {:else if propertyType == 'object'}
    <!-- Object -->
    {@const properties = Object.keys(property.properties ?? {}).filter(
      key => !hiddenProperties?.includes(path + '/' + key)
    )}
    {#each properties as key, i}
      {@const childPath = path + '/' + key}
      <div class:border-b={i < properties.length - 1} class="mt-4 border-gray-300">
        <svelte:self
          bind:value={value[key]}
          path={childPath}
          {schema}
          {hiddenProperties}
          {validationErrors}
          {customComponents}
          {rootValue}
          required={property.required?.includes(key)}
        />
      </div>
    {/each}
  {:else}
    Unknown property: {JSON.stringify(property)}
  {/if}
{/if}

<style lang="postcss">
  :global(.description p) {
    @apply text-sm;
    margin: 1em 0px;
  }
  :global(.bx--toggle-input__label .bx--toggle__switch) {
    @apply mt-0;
  }
</style>
