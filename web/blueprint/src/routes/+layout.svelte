<script lang="ts">
  import ApiErrorModal from '$lib/components/ApiErrorModal.svelte';
  import {apiErrors, queryClient} from '$lib/queries/queryClient';
  import TaskMonitor from '$lib/stores/TaskMonitor.svelte';
  import type {ApiError} from '$lilac';
  import {QueryClientProvider} from '@tanstack/svelte-query';
  import {Theme, ToastNotification} from 'carbon-components-svelte';
  import {onMount} from 'svelte';
  // Styles
  import '../tailwind.css';
  // Carbon component must be imported after tailwind.css
  import {createUrlHashStore, setUrlHashContext, type AppPage} from '$lib/stores/urlHashStore';
  // This import is so we can override the carbon icon theme below.
  import {page} from '$app/stores';
  import Navigation from '$lib/components/Navigation.svelte';
  import {createNavigationStore, setNavigationContext} from '$lib/stores/navigationStore';
  import {createNotificationsStore, setNotificationsContext} from '$lib/stores/notificationsStore';
  import {createSettingsStore, setSettingsContext} from '$lib/stores/settingsStore';
  import 'carbon-components-svelte/css/all.css';
  import {slide} from 'svelte/transition';

  import GoogleAnalytics from '$lib/components/GoogleAnalytics.svelte';
  import {SIDEBAR_TRANSITION_TIME_MS} from '$lib/view_utils';
  import '../app.css';

  let showError: ApiError | undefined = undefined;

  const routeToPage: Record<string, AppPage> = {
    '/': 'home',
    '/datasets': 'datasets',
    '/datasets/loading': 'datasets/loading',
    '/concepts': 'concepts',
    '/signals': 'signals',
    '/settings': 'settings',
    '/rag': 'rag'
  };

  $: currentPage = $page.route.id != null ? routeToPage[$page.route.id] : 'home';
  let urlHashStore = createUrlHashStore();
  setUrlHashContext(urlHashStore);

  const notificationsStore = createNotificationsStore();
  setNotificationsContext(notificationsStore);
  $: notifications = $notificationsStore?.notifications || [];

  onMount(() => {
    // Initialize the page from the hash.
    urlHashStore.setHash(currentPage, $page.url.hash);
  });

  // When the hash changes (back button, click on a link, etc) read the state from the URL and set
  // the dataset state on the global app store.
  function urlChange(url: string | URL) {
    const newURL = new URL(url);
    const newPage = routeToPage[newURL.pathname];
    urlHashStore.setHash(newPage, newURL.hash);
  }

  onMount(() => {
    // This fixes a cross-origin error when the app is embedding in an iframe. Some carbon
    // components attach listeners to window.parent, which is not allowed in an iframe, so we set
    // the parent to window.
    window.parent = window;

    // Handle goto links.
    history.pushState = function (_state, _unused, url) {
      if (url instanceof URL) {
        urlChange(url);
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return History.prototype.pushState.apply(history, arguments as any);
    };
  });

  const settingsStore = createSettingsStore();
  setSettingsContext(settingsStore);

  const navStore = createNavigationStore();
  setNavigationContext(navStore);
</script>

<!-- Monitor for hash changes in the URL. -->
<svelte:window
  on:hashchange={e => urlChange(e.newURL)}
  on:popstate={() => urlChange(location.href)}
/>

<!-- https://carbondesignsystem.com/guidelines/themes/overview#customizing-a-theme -->
<Theme
  theme="white"
  tokens={{
    // Controls the bottom border of the searchbox.
    'border-strong': 'transparent',
    // Typography
    'label-01-letter-spacing': 'var(--cds-productive-heading-01-letter-spacing)',
    'helper-text-01-letter-spacing': 'var(--cds-productive-heading-01-letter-spacing)',
    'productive-heading-01-font-weight': 600
  }}
/>

<QueryClientProvider client={queryClient}>
  <GoogleAnalytics />
  <main class="flex h-screen w-full flex-row">
    {#if $navStore.open}
      <div
        class="flex-shrink-0"
        transition:slide={{axis: 'x', duration: SIDEBAR_TRANSITION_TIME_MS}}
      >
        <Navigation />
      </div>
    {/if}
    <div class="h-full w-full overflow-hidden">
      <slot />
    </div>
  </main>

  <div class="absolute right-2 top-0 z-10 w-96">
    {#each notifications as notification}
      <ToastNotification
        lowContrast
        fullWidth
        title={notification.title}
        subtitle={notification.subtitle || ''}
        caption={notification.message}
        kind={notification.kind}
        timeout={5_000}
        on:close={() => {
          notificationsStore.removeNotification(notification);
        }}
      />
    {/each}
  </div>
  <div class="absolute bottom-4 right-4">
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
  </div>

  <TaskMonitor />
</QueryClientProvider>
