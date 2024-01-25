<script context="module" lang="ts">
  import type {SearchHighlight} from '$lib/view_utils';

  export interface InnerPivot {
    value: string | null;
    count: number;
    textHighlights: SearchHighlight[];
  }

  export interface OuterPivot {
    value: string | null;
    count: number;
    inner: InnerPivot[];
    percentage: string;
    textHighlights: SearchHighlight[];
  }
</script>

<script lang="ts">
  import {getDatasetViewContext, getSelectRowsOptions} from '$lib/stores/datasetViewStore';

  import {queryDatasetSchema} from '$lib/queries/datasetQueries';
  import {datasetLink} from '$lib/utils';
  import type {BinaryFilter, Path, UnaryFilter} from '$lilac';
  import {ArrowUpRight} from 'carbon-icons-svelte';
  import {onDestroy, onMount} from 'svelte';
  import Carousel from '../common/Carousel.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';

  export let filter: BinaryFilter | UnaryFilter;
  export let group: OuterPivot;
  export let path: Path;
  export let numRowsInQuery: number;
  export let itemsPerPage: number;

  let isOnScreen = false;
  let root: HTMLDivElement;
  let observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      isOnScreen = entry.isIntersecting;
    });
  });

  onMount(() => {
    observer.observe(root);
  });

  onDestroy(() => {
    observer.disconnect();
  });

  const store = getDatasetViewContext();
  $: schema = queryDatasetSchema($store.namespace, $store.datasetName);
  $: selectOptions = getSelectRowsOptions($store, $schema?.data);
  $: filters = [filter, ...(selectOptions.filters || [])];

  function getPercentage(count: number, total: number | undefined) {
    if (total == null) return '0';
    return ((count / total) * 100).toFixed(2);
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function castToInnerPivot(item: any): InnerPivot {
    // This is just a type-cast for the svelte component below. We haven't upgraded to the svelte
    // version that supports generics, so we have to do this type-cast.
    return item;
  }
</script>

<div
  class="flex h-full w-full flex-row flex-wrap rounded-lg border border-neutral-200 bg-violet-100 bg-opacity-50 px-4 pb-2 pt-4"
  bind:this={root}
>
  {#if isOnScreen}
    <Carousel items={group.inner} pageSize={itemsPerPage}>
      <div class="w-full" slot="item" let:item>
        {@const innerGroup = castToInnerPivot(item)}
        {@const groupPercentage = getPercentage(innerGroup.count, group.count)}
        {@const totalPercentage = getPercentage(innerGroup.count, numRowsInQuery)}
        {@const groupLink = datasetLink($store.namespace, $store.datasetName, {
          ...$store,
          viewPivot: false,
          pivot: undefined,
          query: {
            ...$store.query,
            filters
          },
          groupBy: {path, value: innerGroup.value}
        })}
        <div
          class="md:1/2 flex h-full w-full max-w-sm flex-grow flex-col justify-between gap-y-4 rounded-lg border border-gray-200 bg-white p-4 shadow"
        >
          <div
            title={innerGroup.value}
            class="card-title h-16 py-0.5 text-base font-normal leading-5 tracking-tight text-neutral-900"
          >
            {#each innerGroup.textHighlights as highlight}
              {#if highlight.isBold}
                <span class="font-bold">{highlight.text}</span>
              {:else}
                <span>{highlight.text}</span>
              {/if}
            {/each}
          </div>
          <div class="flex flex-row gap-x-2 font-light leading-none text-neutral-600">
            <div class="leading-2 flex w-full flex-row text-lg">
              <div class="flex flex-col self-end">
                <div
                  class="leading-2 flex flex-row items-center gap-x-1 text-xl text-neutral-800"
                  use:hoverTooltip={{
                    text: `${groupPercentage}% of ${group.value}\n` + `${totalPercentage}% of total`
                  }}
                >
                  {groupPercentage}%
                </div>
                <span class="text-sm text-neutral-700">
                  {innerGroup.count.toLocaleString()} rows
                </span>
              </div>
            </div>
            <div class="self-end">
              <a
                class="flex flex-row"
                href={groupLink}
                use:hoverTooltip={{
                  text: `Explore ${innerGroup.value} in ${group.value}`
                }}
              >
                <button class="h-8 border border-neutral-300 text-black shadow"
                  ><ArrowUpRight /></button
                ></a
              >
            </div>
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
