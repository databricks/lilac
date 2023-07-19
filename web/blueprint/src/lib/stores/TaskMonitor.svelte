<script lang="ts">
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {queryTaskManifest} from '$lib/queries/taskQueries';
  import {onTasksUpdate} from './taskMonitoringStore';

  const tasks = queryTaskManifest();

  const authInfo = queryAuthInfo();
  $: canRunTasks =
    $authInfo.data?.access.dataset.compute_signals || $authInfo.data?.access.create_dataset;

  $: {
    if ($tasks.isSuccess && canRunTasks) {
      onTasksUpdate($tasks.data);
    }
  }
</script>
