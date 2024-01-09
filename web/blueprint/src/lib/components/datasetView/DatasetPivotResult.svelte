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
  import SvelteCarousel from 'svelte-carousel';

  import {datasetLink} from '$lib/utils';
  import {ROWID, type BinaryFilter, type Path, type UnaryFilter} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import {ChevronLeft, ChevronRight, Information} from 'carbon-icons-svelte';
  import {createEventDispatcher, onDestroy, onMount} from 'svelte';
  import Carousel from '../common/Carousel.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';

  export let filter: BinaryFilter | UnaryFilter;
  export let path: Path;
  export let parentValue: string;
  export let numRowsInQuery: number | undefined;
  // When true, queries will be issued. This allows us to progressively load without spamming the
  // server.
  export let shouldLoad = false;

  const ITEMS_PER_PAGE = 6;

  let isExpanded = true;

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
  $: rowsQuery =
    shouldLoad && isOnScreen
      ? querySelectRows(
          $store.namespace,
          $store.datasetName,
          {...selectOptions, columns: [ROWID], limit: 1, filters},
          $selectRowsSchema.data?.schema
        )
      : null;
  $: numRowsInGroup = $rowsQuery?.data?.total_num_rows;

  $: countQuery =
    shouldLoad && isOnScreen
      ? querySelectGroups($store.namespace, $store.datasetName, {
          leaf_path: path,
          filters,
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
      dispatch('load');
    }
  }

  function getPercentage(count: number, total: number | undefined) {
    if (total == null) return '0';
    return ((count / total) * 100).toFixed(2);
  }

  let currentPage = 0;
  function onPageChange(event: CustomEvent) {
    const page = event.detail;
    currentPage = Math.max(0, page);
  }
  $: console.log('currentpage:', currentPage);
  function pageFromIndex(index: number) {
    console.log('index', index, 'page', Math.floor(index / ITEMS_PER_PAGE));
    return Math.floor(index / ITEMS_PER_PAGE);
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function groupResultFromItem(item: any): (typeof counts)[0] {
    // This is just a type-cast for the svelte component below. We haven't upgraded to the svelte
    // version that supports generics, so we have to do this type-cast.
    return item as (typeof counts)[0];
  }
</script>

<div
  class="flex w-full flex-row flex-wrap"
  class:max-h-screen={!isExpanded}
  class:text-preview-overlay={!isExpanded}
  bind:this={root}
>
  {#if $countQuery?.isFetching}
    <SkeletonText />
  {/if}
  {#if counts.length > 0}
    <Carousel items={counts} pageSize={ITEMS_PER_PAGE}>
      <div class="w-full" slot="item" let:item>
        {@const count = groupResultFromItem(item)}
        {@const groupPercentage = getPercentage(count.count, numRowsInGroup)}
        {@const totalPercentage = getPercentage(count.count, numRowsInQuery)}
        <div class="min-w-64 md:1/2 h-full flex-grow p-1">
          <div
            class="flex h-full w-full max-w-sm flex-col justify-between gap-y-6 rounded-lg border border-gray-200 bg-white p-6 shadow"
          >
            <div class="flex w-full flex-col">
              <div class="h-24">
                <div class="card-title text-lg font-medium leading-6 tracking-tight text-gray-900">
                  {count.name}
                </div>
              </div>
              <div
                class="flex flex-row items-center gap-x-2 font-normal leading-none text-gray-700"
              >
                <div class="leading-2 text-lg">{groupPercentage}%</div>
                <div
                  use:hoverTooltip={{
                    text: `${groupPercentage}% of ${parentValue}\n` + `${totalPercentage}% of total`
                  }}
                >
                  <Information />
                </div>
              </div>
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
      </div>
    </Carousel>
  {/if}
</div>
{#if false}
  <div
    class="flex flex-row flex-wrap"
    class:max-h-screen={!isExpanded}
    class:text-preview-overlay={!isExpanded}
  >
    {#if $countQuery?.isFetching}
      <SkeletonText />
    {/if}
    {#if counts.length > 0}
      <SvelteCarousel
        initialPageIndex={0}
        particlesToShow={ITEMS_PER_PAGE}
        particlesToScroll={ITEMS_PER_PAGE}
        swiping={false}
        on:pageChange={onPageChange}
        let:showPrevPage
        let:showNextPage
      >
        <div slot="prev" class="flex items-center">
          <button class="mx-1" on:click={() => showPrevPage()}><ChevronLeft /></button>
        </div>
        <div slot="next" class="flex items-center">
          <button class="mx-1" on:click={() => showNextPage()}><ChevronRight /></button>
        </div>
        {#each counts as count, i}
          {[console.log('i=', i, count)]}
          {@const groupPercentage = getPercentage(count.count, numRowsInGroup)}
          {@const totalPercentage = getPercentage(count.count, numRowsInQuery)}
          {@const page = pageFromIndex(i)}
          <div
            class="min-w-64 md:1/2 h-full p-1 lg:w-1/6"
            class:hidden={Math.abs(currentPage - page) > 1}
          >
            <div
              class="flex h-full w-full max-w-sm flex-col justify-between gap-y-6 rounded-lg border border-gray-200 bg-white p-6 shadow"
            >
              <div class="flex w-full flex-col">
                <div class="h-24">
                  <div
                    class="card-title text-lg font-medium leading-6 tracking-tight text-gray-900"
                  >
                    {count.name}
                    {i},{page} === {currentPage}
                  </div>
                </div>
                <div
                  class="flex flex-row items-center gap-x-2 font-normal leading-none text-gray-700"
                >
                  <div class="leading-2 text-lg">{groupPercentage}%</div>
                  <div
                    use:hoverTooltip={{
                      text:
                        `${groupPercentage}% of ${parentValue}\n` + `${totalPercentage}% of total`
                    }}
                  >
                    <Information />
                  </div>
                </div>
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
      </SvelteCarousel>
    {/if}
  </div>
{/if}

<style lang="postcss">
  .text-preview-overlay {
    mask-image: linear-gradient(to top, transparent, white 100px);
    z-index: 0 !important;
  }
  .card-title {
    width: 100%;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    background: #fff;
  }
</style>
