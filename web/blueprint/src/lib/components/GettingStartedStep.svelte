<script lang="ts">
  export let stepNumber: number;
  export let title: string;
  export let description: string;
</script>

<div class="flex gap-x-1">
  <div class="font-bold">{stepNumber}.</div>
  <div class="flex flex-col gap-y-1">
    <div class="font-bold">{title}</div>
    <div>{description}</div>
    <slot />
  </div>
</div>
