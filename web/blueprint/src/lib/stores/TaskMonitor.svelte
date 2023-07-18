<script lang="ts">
  import {queryUserAcls} from '$lib/queries/serverQueries';
  import {queryTaskManifest} from '$lib/queries/taskQueries';
  import {onTasksUpdate} from './taskMonitoringStore';

  const tasks = queryTaskManifest();

  const userAcls = queryUserAcls();
  $: canRunTasks = $userAcls.data?.dataset.compute_signals || $userAcls.data?.create_dataset;

  $: {
    if ($tasks.isSuccess && canRunTasks) {
      onTasksUpdate($tasks.data);
    }
  }
</script>
