<script lang="ts">
  import {apiErrors} from '$lib/queries/queryClient';
  import {ToastNotification} from 'carbon-components-svelte';

  import {queryServerStatus} from '$lib/queries/serverQueries';
  import type {ApiError} from '$lilac';
  import ApiErrorModal from './ApiErrorModal.svelte';

  let showError: ApiError | undefined = undefined;

  $: serverStatus = queryServerStatus();
  $: isProdMode = $serverStatus.data?.prod_mode;
</script>

{#if !isProdMode}
  {#each $apiErrors as error}
    <ToastNotification
      lowContrast
      title={error.name || 'Error'}
      subtitle={error.body.message || error.message}
      on:close={() => {
        $apiErrors = $apiErrors.filter(e => e !== error);
      }}
    >
      <div slot="caption">
        <button class="underline" on:click={() => (showError = error)}>Show error</button>
      </div>
    </ToastNotification>
  {/each}
  {#if showError}
    <ApiErrorModal error={showError} />
  {/if}
{/if}
