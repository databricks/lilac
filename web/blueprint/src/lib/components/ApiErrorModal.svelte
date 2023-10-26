<script lang="ts">
  import type {ApiError} from '$lilac';
  import {
    Modal,
    StructuredList,
    StructuredListBody,
    StructuredListCell,
    StructuredListRow
  } from 'carbon-components-svelte';

  export let error: ApiError;
</script>

<Modal passiveModal open={!!error} modalHeading={error.name}>
  <StructuredList>
    <StructuredListBody>
      <StructuredListRow>
        <StructuredListCell>details</StructuredListCell>
        <StructuredListCell class="whitespace-break-spaces">{error.body.detail}</StructuredListCell>
      </StructuredListRow>
      <StructuredListRow>
        <StructuredListCell>url</StructuredListCell>
        <StructuredListCell>{error.request.method} {error.request.url}</StructuredListCell>
      </StructuredListRow>
      <StructuredListRow>
        <StructuredListCell>status</StructuredListCell>
        <StructuredListCell>{error.status} {error.statusText}</StructuredListCell>
      </StructuredListRow>
      <StructuredListRow>
        <StructuredListCell>path</StructuredListCell>
        <StructuredListCell class="whitespace-pre"
          >{JSON.stringify(error.request.path, null, 2)}</StructuredListCell
        >
      </StructuredListRow>
      <StructuredListRow>
        <StructuredListCell>body</StructuredListCell>
        <StructuredListCell class="whitespace-pre"
          >{JSON.stringify(error.request.body, null, 2)}</StructuredListCell
        >
      </StructuredListRow>
    </StructuredListBody>
  </StructuredList>
</Modal>
