<script>
	import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query';
	import '../app.css';

	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				refetchOnWindowFocus: false
			}
		}
	});
</script>

<QueryClientProvider client={queryClient}>
	<main class="h-screen flex flex-col">
		<div class="navbar bg-base-100">
			<a class="btn btn-ghost normal-case text-xl">Lilac Inspector</a>
		</div>

		<div class="overflow-y-scroll">
			<slot />
		</div>
	</main>
</QueryClientProvider>
