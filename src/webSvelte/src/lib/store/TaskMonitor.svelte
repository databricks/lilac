<script lang="ts">
  import {useGetTaskManifestQuery} from './apiServer';
  import {onTasksUpdate} from './taskMonitoring';

  const tasks = useGetTaskManifestQuery();

  $: {
    if ($tasks.isSuccess) {
      onTasksUpdate($tasks.data);
    }
  }
</script>
