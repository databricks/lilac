<script lang="ts">
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {Button, OverflowMenu, OverflowMenuItem} from 'carbon-components-svelte';
  /**
   * The component for a page, including a header with slots for subtext, center, and right.
   */
  import {googleLogoutMutation} from '$lib/queries/googleAuthQueries';
  import {getNavigationContext} from '$lib/stores/navigationStore';
  import {SidePanelOpen} from 'carbon-icons-svelte';
  import TaskStatus from './TaskStatus.svelte';
  import Commands from './commands/Commands.svelte';
  import {hoverTooltip} from './common/HoverTooltip';

  const authInfo = queryAuthInfo();
  $: navStore = getNavigationContext();

  const origin = location.origin;
  const loginUrl = `${origin}/google/login?origin_url=${origin}`;
  const logoutMutation = googleLogoutMutation();
  function logout() {
    $logoutMutation.mutate([]);
  }
  // When in an iframe, boot the user out to a new tab with the login URL since we cannot set the
  // session cookie in the iframe.
  const inIframe = window.self !== window.top;
  const loginTarget = inIframe ? '_blank' : '';
</script>

<div class="flex h-full w-full flex-col">
  <!-- Header -->
  <div
    class="header flex w-full flex-initial flex-row items-center justify-between justify-items-center border-b border-gray-200"
  >
    <button
      class:invisible={$navStore.open}
      class="ml-1 opacity-60 hover:bg-gray-200"
      use:hoverTooltip={{text: 'Open sidebar'}}
      on:click={() => ($navStore.open = true)}><SidePanelOpen /></button
    >
    <div
      class="ml-1 flex flex-grow flex-row items-center justify-between justify-items-center gap-x-12 py-2 pr-4"
    >
      <div class="mr-4 flex flex-row items-center">
        <div class="mt-1">
          <slot name="header-subtext" />
        </div>
      </div>
      <div class="flex-grow flex-row items-center justify-center">
        <slot name="header-center" />
      </div>
      <div class="flex flex-row items-center gap-x-2">
        <slot name="header-right" />
        <TaskStatus />
        {#if $authInfo.data?.auth_enabled}
          {#if $authInfo.data?.user != null}
            <div class="flex h-9 flex-row items-center rounded border border-neutral-200">
              <div
                class="ml-2 mr-1 flex"
                use:hoverTooltip={{
                  text: `Logged into Google as ${$authInfo.data?.user.name} with email ${$authInfo.data?.user.email}`
                }}
              >
                {$authInfo.data?.user.given_name}
              </div>
              <div>
                <OverflowMenu flipped>
                  <OverflowMenuItem on:click={logout} class="optionOne" text="Logout" />
                </OverflowMenu>
              </div>
            </div>
          {:else}
            <Button size="small" href={loginUrl} target={loginTarget}>Login</Button>
          {/if}
        {/if}
      </div>
    </div>
  </div>

  <!-- Body -->
  <div class="relative flex h-full w-full overflow-hidden">
    <slot />
  </div>

  <Commands />
</div>
