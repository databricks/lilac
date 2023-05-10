<script lang="ts">
  import type {JSONSchema4Type, JSONSchema7Definition} from 'json-schema';
  import {Draft07, type Draft, type JSONError} from 'json-schema-library';
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

  // Parse the JSON schema
  $: jsonSchema = typeof schema === 'object' ? new Draft07(schema) : null;

  // Reset schema values whenever the schema
  $: {
    if (jsonSchema) setValueDefaults(jsonSchema);
  }

  // Validate the schema values when values update
  $: validationErrors = jsonSchema ? jsonSchema.validate(value) : [];

  // Reset the source schema property values with defaults
  function setValueDefaults(jsonSchema: Draft) {
    value = jsonSchema.getTemplate(value);
  }
</script>

{#if jsonSchema}
  <JsonSchemaInput
    bind:value
    schema={jsonSchema}
    {hiddenProperties}
    {showDescription}
    {validationErrors}
  />
{/if}
