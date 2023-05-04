<script lang="ts">
	import { page } from '$app/stores';
	import Spinner from '$lib/components/Spinner.svelte';
	import RowView from '$lib/components/datasetView/RowView.svelte';
	import SchemaView from '$lib/components/schemaView/SchemaView.svelte';
	import { useGetManifestQuery } from '$lib/store/apiDataset';

	$: namespace = $page.params.namespace;
	$: datasetName = $page.params.datasetName;

	$: manifset = useGetManifestQuery(namespace, datasetName);
</script>

<div class="flex h-full w-full">
	<div class="w-1/2 h-full border-r border-gray-200 border-solid">
		<SchemaView {namespace} {datasetName} />
	</div>
	<div class="w-1/2 h-full p-4">
		{#if $manifset.isLoading}
			<Spinner />
		{:else}
			<RowView {namespace} {datasetName} />
		{/if}
	</div>
</div>
