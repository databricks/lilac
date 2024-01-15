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

  import {datasetLink} from '$lib/utils';
  import {getSearchHighlighting} from '$lib/view_utils';
  import {ROWID, type BinaryFilter, type Path, type StringFilter, type UnaryFilter} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import {Information} from 'carbon-icons-svelte';
  import {createEventDispatcher, onDestroy, onMount} from 'svelte';
  import Carousel from '../common/Carousel.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';

  export let filter: BinaryFilter | UnaryFilter;
  export let path: Path;
  export let parentValue: string;
  export let numRowsInQuery: number | undefined;
  export let searchText: string | undefined;

  const ITEMS_PER_PAGE = 5;

  let isOnScreen = false;
  let root: HTMLDivElement;
  let observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        isOnScreen = true;
        observer.disconnect();
      }
    });
  });

  onMount(() => {
    observer.observe(root);
  });

  onDestroy(() => {
    observer.disconnect();
  });

  const store = getDatasetViewContext();

  $: selectRowsSchema = querySelectRowsSchema(
    $store.namespace,
    $store.datasetName,
    getSelectRowsSchemaOptions($store)
  );

  $: filters = [filter, ...(selectOptions.filters || [])];

  $: selectOptions = getSelectRowsOptions($store);
  $: rowsQuery = isOnScreen
    ? querySelectRows(
        $store.namespace,
        $store.datasetName,
        {...selectOptions, columns: [ROWID], limit: 1, filters},
        $selectRowsSchema.data?.schema
      )
    : null;
  $: numRowsInGroup = $rowsQuery?.data?.total_num_rows;

  $: countQuery = isOnScreen
    ? querySelectGroups($store.namespace, $store.datasetName, {
        leaf_path: path,
        filters: [
          ...filters,
          ...(searchText ? [{path, op: 'ilike', value: searchText} as StringFilter] : [])
        ],
        // Explicitly set the limit to null to get all the groups, not just the top 100.
        limit: null
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
      dispatch('load', {count: counts.length});
    }
  }

  function getPercentage(count: number, total: number | undefined) {
    if (total == null) return '0';
    return ((count / total) * 100).toFixed(2);
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function groupResultFromItem(item: any): (typeof counts)[0] {
    // This is just a type-cast for the svelte component below. We haven't upgraded to the svelte
    // version that supports generics, so we have to do this type-cast.
    return item as (typeof counts)[0];
  }
</script>

<div class="flex h-64 w-full flex-row flex-wrap" bind:this={root}>
  {#if $countQuery?.isFetching === true}
    <SkeletonText paragraph class="w-full" />
  {/if}
  {#if counts.length > 0}
    <Carousel items={counts} pageSize={ITEMS_PER_PAGE}>
      <div class="w-full" slot="item" let:item>
        {@const count = groupResultFromItem(item)}
        {@const groupPercentage = getPercentage(count.count, numRowsInGroup)}
        {@const totalPercentage = getPercentage(count.count, numRowsInQuery)}
        {@const textHighlights = getSearchHighlighting(count.name, searchText)}
        <div
          class="md:1/2 flex h-full w-full max-w-sm flex-grow flex-col justify-between gap-y-4 rounded-lg border border-gray-200 bg-white p-6 shadow"
        >
          <div
            class="card-title h-16 text-center text-base font-light leading-5 tracking-tight text-neutral-900"
          >
            {#each textHighlights as highlight}
              {#if highlight.isBold}
                <span class="font-bold">{highlight.text}</span>
              {:else}
                <span>{highlight.text}</span>
              {/if}
            {/each}
          </div>
          <div
            class="flex flex-row items-center justify-center gap-x-2 font-light leading-none text-neutral-600"
          >
            <div class="leading-2 text-lg">
              <div class="flex flex-col py-2">
                <div class="leading-2 flex flex-row items-center gap-x-1 text-xl text-neutral-800">
                  {groupPercentage}%
                  <div
                    use:hoverTooltip={{
                      text:
                        `${groupPercentage}% of ${parentValue}\n` + `${totalPercentage}% of total`
                    }}
                  >
                    <Information />
                  </div>
                </div>
                <span class="text-sm text-neutral-700">
                  {count.count.toLocaleString()} rows
                </span>
              </div>
            </div>
          </div>
          <div class="w-full text-center">
            <a
              target="_blank"
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
              Explore
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
      </div>
    </Carousel>
  {/if}
</div>

<style lang="postcss">
  .card-title {
    width: 100%;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    background: #fff;
  }
</style>
