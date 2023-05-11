<script lang="ts">
  import {queryTaskManifest} from '$lib/queries/taskQueries';
  import {onTasksUpdate} from './taskMonitoringStore';

  const tasks = queryTaskManifest();

  $: {
    if ($tasks.isSuccess) {
      onTasksUpdate($tasks.data);
    }
  }
</script>
