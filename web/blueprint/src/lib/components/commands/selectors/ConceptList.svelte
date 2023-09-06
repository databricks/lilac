<script lang="ts">
  import {queryConcepts} from '$lib/queries/conceptQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {getTaggedConcepts} from '$lib/view_utils';
  import type {ConceptInfo} from '$lilac';
  import {Tag} from 'carbon-components-svelte';
  import CommandSelectList from './CommandSelectList.svelte';

  export let selectedConceptInfo: ConceptInfo | undefined = undefined;

  const concepts = queryConcepts();
  const authInfo = queryAuthInfo();
  $: userId = $authInfo.data?.user?.id;
  $: username = $authInfo.data?.user?.given_name;

  $: selectedConceptInfo = $concepts.data?.[0];

  // Sort the concepts by the same sort order as navigation.
  $: taggedConcepts = getTaggedConcepts(null, $concepts.data || [], userId, username);
  let items: CommandSelectList['items'][] = [];
  $: {
    items = [];
    for (const tag of taggedConcepts) {
      for (const group of tag.groups) {
        for (const item of group.items) {
          items.push({
            title: item.name,
            value: item
          });
        }
      }
    }
  }
</script>

{#if $concepts.data}
  {#each taggedConcepts as { tag, groups }}
    {#if tag != ''}
      <div
        class="flex flex-row justify-between pl-3
text-sm opacity-80"
      >
        <div class="py-1">
          <Tag type="purple" size="sm">{tag}</Tag>
        </div>
      </div>
    {/if}
    {#each groups as { group, items }}
      <div
        class="flex flex-row justify-between pl-7
        text-sm opacity-80"
      >
        <div class="py-1">
          {group}
        </div>
      </div>
      <div class="w-full truncate py-1 pl-6 text-black">
        <CommandSelectList
          items={items.map(item => ({
            title: item.item.name,
            value: item.item
          }))}
          item={selectedConceptInfo}
          on:select={e => (selectedConceptInfo = e.detail)}
        />
      </div>
    {/each}
  {/each}
{:else if $concepts.isLoading}
  <CommandSelectList skeleton />
{/if}
