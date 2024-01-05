<script lang="ts">
  import {
    querySelectGroups,
    querySelectRows,
    querySelectRowsSchema,
    querySettings
  } from '$lib/queries/datasetQueries';
  import {
    getDatasetViewContext,
    getSelectRowsOptions,
    getSelectRowsSchemaOptions
  } from '$lib/stores/datasetViewStore';
  import {datasetLink} from '$lib/utils';
  import {getHighlightedFields, getMediaFields} from '$lib/view_utils';
  import {
    L,
    ROWID,
    childFields,
    deserializePath,
    isSignalField,
    serializePath,
    valueAtPath,
    type Path
  } from '$lilac';
  import {Select, SelectItem, SkeletonText} from 'carbon-components-svelte';
  import DatasetPivotResult from './DatasetPivotResult.svelte';

  let outerLeafPath: Path | undefined = undefined; // = ['source'];
  let innerLeafPath: Path | undefined = undefined; // ['prompt_cluster', 'topic'];

  const store = getDatasetViewContext();

  $: settings = querySettings($store.namespace, $store.datasetName);
  $: mediaFields = $settings.data
    ? getMediaFields($selectRowsSchema?.data?.schema, $settings.data)
    : [];
  $: highlightedFields = getHighlightedFields($store.query, $selectRowsSchema?.data);

  $: selectRowsSchema = querySelectRowsSchema(
    $store.namespace,
    $store.datasetName,
    getSelectRowsSchemaOptions($store)
  );

  $: fields = $selectRowsSchema.data?.schema
    ? childFields($selectRowsSchema.data.schema).filter(
        f => !isSignalField(f) && f.dtype != null && f.path[0] !== ROWID
      )
    : null;

  $: selectOptions = getSelectRowsOptions($store);
  $: rowsQuery = querySelectRows(
    $store.namespace,
    $store.datasetName,
    {...selectOptions, columns: [ROWID], limit: 1},
    $selectRowsSchema.data?.schema
  );
  $: numRowsInQuery = $rowsQuery.data?.total_num_rows;
  $: rowIds = $rowsQuery.data?.rows.map(row => L.value(valueAtPath(row, [ROWID])!, 'string')!);

  // Get the total count for the dataset.

  $: outerCountQuery =
    outerLeafPath != null
      ? querySelectGroups($store.namespace, $store.datasetName, {
          leaf_path: outerLeafPath,
          filters: selectOptions.filters
        })
      : null;
  $: outerCounts = ($outerCountQuery?.data?.counts || []).map(([name, count]) => ({
    name,
    count
  }));

  function getPercentage(count: number) {
    if (numRowsInQuery == null) return '';
    return ((count / numRowsInQuery) * 100).toFixed(2);
  }

  $: outerLeafPathId = outerLeafPath ? serializePath(outerLeafPath) : undefined;
  $: innerLeafPathId = innerLeafPath ? serializePath(innerLeafPath) : undefined;

  $: {
    // Auto-select the first field.
    if (fields != null && fields.length > 0 && outerLeafPath == null) {
      if ($store.pivot?.outerPath != null) {
        outerLeafPath = $store.pivot.outerPath;
      } else {
        outerLeafPath = fields[0].path;
      }
      if ($store.pivot?.innerPath != null) {
        innerLeafPath = $store.pivot.innerPath;
      } else {
        innerLeafPath = fields[1].path;
      }
    }
  }

  function outerFieldSelected(e: Event) {
    const val = (e.target as HTMLInputElement).value;
    outerLeafPath = deserializePath(val);

    $store.pivot = {outerPath: outerLeafPath, innerPath: $store.pivot?.innerPath};
  }
  function innerFieldSelected(e: Event) {
    const val = (e.target as HTMLInputElement).value;
    innerLeafPath = deserializePath(val);
    $store.pivot = {innerPath: innerLeafPath, outerPath: $store.pivot?.outerPath};
  }

  // We use a loadIndex to load the inner viewers serially so we don't overwhelm the server.
  export let loadIndex = 0;
</script>

<div class="h-full">
  <div class="mx-10 mb-4 flex w-96 flex-row gap-x-4">
    <Select
      size={'sm'}
      labelText="Outer field"
      on:change={outerFieldSelected}
      selected={outerLeafPathId}
    >
      {#each fields || [] as field}
        <SelectItem value={serializePath(field.path)} />
      {/each}
    </Select>

    <Select
      size={'sm'}
      labelText="Inner field"
      on:change={innerFieldSelected}
      selected={innerLeafPathId}
    >
      <SelectItem value={undefined} />

      {#each fields || [] as field}
        <SelectItem value={serializePath(field.path)} />
      {/each}
    </Select>
  </div>

  <div class="flex h-full flex-row">
    {#if $outerCountQuery == null || $outerCountQuery.isFetching || outerLeafPath == null}
      <SkeletonText />
    {:else}
      <div class="flex h-full w-full flex-col overflow-y-scroll">
        {#each outerCounts as outerCount, i}
          {@const groupLink = datasetLink($store.namespace, $store.datasetName, {
            ...$store,
            viewPivot: false,
            pivot: undefined,
            query: {
              ...$store.query
            },
            groupBy: {path: outerLeafPath, value: outerCount.name}
          })}
          {@const percentage = getPercentage(outerCount.count)}
          <div class="mb-4 flex w-full flex-col px-4">
            <div class="text-preview-overlay sticky top-0 z-50 mx-6">
              <div class="absolute left-0 top-0 z-10 h-full w-full bg-white" />
              <div
                class="absolute left-0 top-0 z-10 h-full w-full bg-blue-100"
                style={`width: ${percentage}%`}
              />
              <div
                class="relative left-0 top-0 z-50 py-2 leading-none tracking-tight text-gray-900"
              >
                <span class="mx-2 text-2xl"
                  >{outerCount.name}
                  <a class="inline-block" href={groupLink}>
                    <svg
                      class="ms-2 h-3 w-3 rtl:rotate-[270deg]"
                      aria-hidden="true"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 18 18"
                    >
                      <path
                        stroke="currentColor"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M15 11v4.833A1.166 1.166 0 0 1 13.833 17H2.167A1.167 1.167 0 0 1 1 15.833V4.167A1.166 1.166 0 0 1 2.167 3h4.618m4.447-2H17v5.768M9.111 8.889l7.778-7.778"
                      />
                    </svg>
                  </a>
                </span>
                <span class="ml-2 text-lg">({percentage}%)</span>
              </div>
            </div>
            <div>
              {#if innerLeafPath && innerLeafPath.length > 0}
                <DatasetPivotResult
                  shouldLoad={loadIndex >= i}
                  on:load={() => {
                    // Serially load in the order of results on the page so we don't overwhelm the
                    // server.
                    loadIndex = i + 1;
                  }}
                  filter={outerCount.name == null
                    ? {path: outerLeafPath, op: 'not_exists'}
                    : {path: outerLeafPath, op: 'equals', value: outerCount.name}}
                  path={innerLeafPath}
                  {numRowsInQuery}
                />
              {/if}
            </div>
          </div>
        {/each}
      </div>
      <!-- <div class="h-full w-1/2 overflow-y-scroll">
        {#if rowIds}
          <SingleItemView selectRowsOptions={selectOptions} hideControls />
        {/if}
      </div> -->
    {/if}
  </div>
</div>
