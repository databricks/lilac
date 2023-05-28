<script lang="ts">
  import {queryDatasetSchema, queryManyDatasetStats} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext, isPathVisible} from '$lib/stores/datasetViewStore';
  import {listFields, serializePath, type Path} from '$lilac';
  import {Button, TextInput} from 'carbon-components-svelte';
  import {Close} from 'carbon-icons-svelte';
  import {onMount} from 'svelte';

  let datasetViewStore = getDatasetViewContext();

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);

  let visibleStringFields: Path[] = [];
  $: {
    let allFields = $schema?.isSuccess ? listFields($schema.data) : [];
    visibleStringFields = allFields
      .filter(f => isPathVisible($datasetViewStore.visibleColumns, f.path, undefined))
      .filter(f => f.dtype == 'string')
      .map(f => f.path);
  }

  $: statsQueries = queryManyDatasetStats(
    visibleStringFields.map(path => {
      return [
        $datasetViewStore.namespace,
        $datasetViewStore.datasetName,
        {
          leaf_path: path
        }
      ];
    })
  );

  // TODO(nsthorat): Allow this to be a selection. Currently we just choose the longest string path.
  let selectedSearchPath: string | null = null;
  $: {
    if ($statsQueries && $statsQueries.length > 0 && $statsQueries.every(q => q.isSuccess)) {
      const stats = $statsQueries.map(q => q.data);
      const pathLengths = stats
        .map((s, i) => {
          return {
            path: visibleStringFields[i],
            avg_text_length: s?.avg_text_length || 0
          };
        })
        .sort((a, b) => {
          return b.avg_text_length - a.avg_text_length;
        });

      selectedSearchPath = serializePath(pathLengths[0].path);
    } else {
      selectedSearchPath = null;
    }
  }

  // Copy filters from query options
  let searchText: string;
  onMount(() => {
    const searches = structuredClone($datasetViewStore.queryOptions.searches || []);
    // TODO(nsthorat): support multiple searches.
    searchText = searches.length > 0 ? searches[0].query : '';
  });

  const search = () => {
    if (selectedSearchPath == null) {
      return;
    }
    if (searchText == '') {
      $datasetViewStore.queryOptions.searches = [];
      return;
    }
    $datasetViewStore.queryOptions.searches = [
      {
        path: [selectedSearchPath],
        type: 'contains',
        query: searchText
      }
    ];
  };
</script>

<div class="search-container mx-4 mb-2 flex flex-row items-end">
  <TextInput
    labelText={selectedSearchPath == null
      ? 'Select a text field to search'
      : `Search "${selectedSearchPath}"`}
    disabled={selectedSearchPath == null}
    bind:value={searchText}
    on:keydown={e => (e.key == 'Enter' ? search() : null)}
    size="sm"
  />
  <div class=" -ml-6 mr-2 flex h-8 items-center">
    <button
      class="z-10 opacity-50 hover:opacity-100"
      class:opacity-20={selectedSearchPath == null}
      class:hover:opacity-20={selectedSearchPath == null}
      class:invisible={searchText == '' || searchText == null}
      on:click|stopPropagation={() => {
        searchText = '';
        search();
      }}
    >
      <Close />
    </button>
  </div>
  <div class="ml-2">
    <Button
      disabled={selectedSearchPath == null}
      kind="ghost"
      size="small"
      on:click={() => search()}>Search</Button
    >
  </div>
</div>

<style lang="postcss">
  .search-container {
    width: 30rem;
  }
</style>
