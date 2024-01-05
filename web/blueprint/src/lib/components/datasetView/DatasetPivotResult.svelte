<script lang="ts">
  import {
    querySelectGroups,
    querySelectRows,
    querySelectRowsSchema
  } from '$lib/queries/datasetQueries';
  import {
    getDatasetViewContext,
    getSelectRowsOptions,
    getSelectRowsSchemaOptions
  } from '$lib/stores/datasetViewStore';
  import Carousel from 'svelte-carousel';

  import {datasetLink} from '$lib/utils';
  import {ROWID, type BinaryFilter, type Path, type UnaryFilter} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import {createEventDispatcher} from 'svelte';

  export let filter: BinaryFilter | UnaryFilter;
  export let path: Path;
  export let numRowsInQuery: number | undefined;
  // When true, queries will be issued. This allows us to progressively load without spamming the
  // server.
  export let shouldLoad = false;

  let isExpanded = true;

  const store = getDatasetViewContext();

  $: selectRowsSchema = querySelectRowsSchema(
    $store.namespace,
    $store.datasetName,
    getSelectRowsSchemaOptions($store)
  );

  $: filters = [filter, ...(selectOptions.filters || [])];

  $: selectOptions = getSelectRowsOptions($store);
  $: rowsQuery = shouldLoad
    ? querySelectRows(
        $store.namespace,
        $store.datasetName,
        {...selectOptions, columns: [ROWID], limit: 1, filters},
        $selectRowsSchema.data?.schema
      )
    : null;
  $: numRowsInGroup = $rowsQuery?.data?.total_num_rows;

  $: countQuery = shouldLoad
    ? querySelectGroups($store.namespace, $store.datasetName, {
        leaf_path: path,
        filters
      })
    : null;
  $: counts = ($countQuery?.data?.counts || []).map(([name, count]) => ({
    name,
    count
  }));

  const dispatch = createEventDispatcher();
  $: {
    if (
      $rowsQuery?.data != null &&
      $rowsQuery?.isFetching === false &&
      $countQuery?.data != null &&
      $countQuery?.isFetching === false
    ) {
      dispatch('load');
    }
  }

  function getPercentage(count: number, total: number | undefined) {
    if (total == null) return '0';
    return ((count / total) * 100).toFixed(2);
  }
</script>

<div
  class="-mx-3 flex flex-row flex-wrap"
  class:max-h-screen={!isExpanded}
  class:text-preview-overlay={!isExpanded}
>
  {#if $countQuery?.isFetching}
    <SkeletonText />
  {/if}
  {#if counts.length > 0}
    <Carousel particlesToShow="6" particlesToScroll="6" swiping={false}>
      {#each counts as count}
        {@const groupPercentage = getPercentage(count.count, numRowsInGroup)}
        {@const totalPercentage = getPercentage(count.count, numRowsInQuery)}
        <div class="min-w-64 md:1/2 p-1 lg:w-1/6">
          <div
            class="flex w-full max-w-sm flex-col rounded-lg border border-gray-200 bg-white p-6 shadow"
          >
            <div class="relative flex w-full items-center">
              <div class="relative left-0 top-0 z-10 flex h-full flex-row items-center">
                <div class="py-1 text-lg font-medium leading-none tracking-tight text-gray-900">
                  {count.name}
                </div>
              </div>
            </div>
            <div class="h-16">
              <p class="font-normal text-gray-700">
                {groupPercentage}% of group
              </p>
              <p class="font-normal text-gray-700">
                {totalPercentage}% of total
              </p>
            </div>
            <a
              href={datasetLink($store.namespace, $store.datasetName, {
                ...$store,
                viewPivot: false,
                pivot: undefined,
                query: {
                  ...$store.query,
                  filters
                },
                groupBy: {path, value: count.name}
              })}
              class="inline-flex items-center text-blue-600 hover:underline"
            >
              Browse
              <svg
                class="ms-2.5 h-3 w-3 rtl:rotate-[270deg]"
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
          </div>
        </div>
      {/each}
    </Carousel>
  {/if}
</div>

<style lang="postcss">
  .text-preview-overlay {
    mask-image: linear-gradient(to top, transparent, white 100px);
    z-index: 0 !important;
  }
</style>
