<script lang="ts">
  import { useGetSchemaQuery } from '$lib/store/apiDataset';
  import { getDatasetViewContext } from '$lib/store/datasetViewStore';
  import {
    ENRICHMENT_TYPE_TO_VALID_DTYPES,
    listFields,
    pathIsEqual,
    type EnrichmentType,
    type LilacSchemaField,
    type Path
  } from '$lilac';
  import { Select, SelectItem } from 'carbon-components-svelte';
  import { onMount } from 'svelte';

  export let labelText = 'Field';
  export let helperText: string | undefined = undefined;
  export let enrichmentType: EnrichmentType | undefined = undefined;
  export let filter: ((field: LilacSchemaField) => boolean) | undefined = undefined;

  export let defaultPath: Path | undefined = undefined;
  export let path: Path | undefined = undefined;

  const datasetViewStore = getDatasetViewContext();

  $: schema = useGetSchemaQuery($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: fields = $schema.isSuccess
    ? listFields($schema.data)
        .filter((field) => field.path.length > 0)
        .filter((field) =>
          enrichmentType
            ? field.dtype && ENRICHMENT_TYPE_TO_VALID_DTYPES[enrichmentType].includes(field.dtype)
            : true
        )
    : [];

  function formatField(field: LilacSchemaField): string {
    return `${field.path.join('.')} (${field.dtype})`;
  }

  let inFilterLeafs: LilacSchemaField[] = [];
  let outFilterLeafs: LilacSchemaField[] = [];

  $: {
    inFilterLeafs = [];
    outFilterLeafs = [];

    if (filter) {
      for (const leaf of fields || []) {
        if (filter(leaf)) {
          inFilterLeafs.push(leaf);
        } else {
          outFilterLeafs.push(leaf);
        }
      }
    } else {
      inFilterLeafs.push(...(fields || []));
    }
  }

  $: options = [
    ...inFilterLeafs.map((f) => ({
      value: f,
      label: formatField(f),
      disabled: false
    })),
    ...outFilterLeafs.map((f) => ({
      value: f,
      label: formatField(f),
      disabled: true
    }))
  ];

  let selectedIndex = 0;

  onMount(async () => {
    const defaultSelection = options.findIndex((f) => pathIsEqual(f.value.path, defaultPath));
    if (defaultSelection >= 0) {
      selectedIndex = defaultSelection;
    } else {
      selectedIndex = 0;
    }
  });

  $: path = options[selectedIndex]?.value.path;
</script>

<Select {labelText} {helperText} bind:selected={selectedIndex} required>
  {#each options as option, i}
    <SelectItem value={i} disabled={option.disabled} text={option.label} />
  {/each}
</Select>
