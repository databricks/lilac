<script lang="ts">
  import { useGetDatasetsQuery } from '$lib/store/apiDataset';

  const datasets = useGetDatasetsQuery();
</script>

<ul>
  {#if $datasets.isSuccess}
    {#each $datasets.data as row}
      <li>
        <a href="/datasets/{row.namespace}/{row.dataset_name}">
          {row.namespace}/{row.dataset_name}
        </a>
      </li>
    {/each}
  {/if}
</ul>
