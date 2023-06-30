<script lang="ts">
  import type {JSONSchema4Type, JSONSchema7, JSONSchema7Definition} from 'json-schema';
  import {Draft07, type Draft, type JSONError} from 'json-schema-library';
  import type {SvelteComponent} from 'svelte';
  import JsonSchemaInput from './JSONSchemaInput.svelte';

  /** The schema to render form for */
  export let schema: JSONSchema7Definition;
  /** The value produced by the form. Useful to bind to. */
  export let value: Record<string, JSONSchema4Type> = {};
  /** The properties to hide from the form */
  export let hiddenProperties: string[] = [];
  /** The validation errors */
  export let validationErrors: JSONError[] = [];
  /** Whether to show the top level description */
  export let showDescription = true;
  export let customComponents: Record<string, typeof SvelteComponent> = {};

  // Parse the JSON schema
  $: jsonSchema = typeof schema === 'object' ? new Draft07(schema) : null;

  // Reset schema values whenever the schema changes.
  $: {
    if (jsonSchema) setValueDefaults(jsonSchema);
  }

  // Validate the schema values when values update.
  $: validationErrors = jsonSchema ? jsonSchema.validate(value) : [];

  // Reset the source schema property values with defaults
  function setValueDefaults(jsonSchema: Draft) {
    value = jsonSchema.getTemplate(value, undefined, {addOptionalProps: false});
    for (const [propertyName, property] of Object.entries(
      (schema as JSONSchema7).properties || {}
    )) {
      const defaultValue = (property as JSONSchema7).default;
      if (defaultValue && value[propertyName] != defaultValue) {
        value[propertyName] = defaultValue;
      }
    }
  }
</script>

{#if jsonSchema}
  <JsonSchemaInput
    bind:value
    schema={jsonSchema}
    {hiddenProperties}
    {showDescription}
    {validationErrors}
    {customComponents}
    rootValue={value}
  />
{/if}
