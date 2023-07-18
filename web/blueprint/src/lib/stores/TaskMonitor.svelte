<script lang="ts">
  import {queryServerStatus} from '$lib/queries/serverQueries';
  import {queryTaskManifest} from '$lib/queries/taskQueries';
  import {onTasksUpdate} from './taskMonitoringStore';

  const tasks = queryTaskManifest();
  const serverStatus = queryServerStatus();
  $: isServerReadonly = $serverStatus.data?.read_only ?? true;

  $: {
    if ($tasks.isSuccess && !isServerReadonly) {
      onTasksUpdate($tasks.data);
    }
  }
</script>
