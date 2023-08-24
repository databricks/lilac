<script lang="ts">
  import {queryDatasets} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {datasetLink} from '$lib/utils';
  import {Button, SkeletonText} from 'carbon-components-svelte';
  import {Help} from 'carbon-icons-svelte';
  import WelcomeBanner from './WelcomeBanner.svelte';
  import {hoverTooltip} from './common/HoverTooltip';

  const tryDataset = {
    namespace: 'lilac',
    name: 'OpenOrca-100k',
    displayName: 'OpenOrca',
    originalLink: 'https://huggingface.co/datasets/Open-Orca/OpenOrca'
  };
  const tryLink = datasetLink(tryDataset.namespace, tryDataset.name);
  const authInfo = queryAuthInfo();
  $: huggingFaceSpaceId = $authInfo.data?.huggingface_space_id;

  const datasets = queryDatasets();

  $: hasTryDataset = ($datasets.data || []).some(
    d => d.namespace === tryDataset.namespace && d.dataset_name === tryDataset.name
  );
</script>

<div class="mx-32 flex w-full flex-col items-center gap-y-6 px-8">
  <div class="mt-8 w-full text-center">
    <h2>Welcome to Lilac</h2>
    <div class="mt-2 text-base text-gray-700">analyze, structure and clean data with AI</div>
    <div class="mt-2 text-sm text-gray-700">
      <a target="_blank" href="https://lilacml.com">visit our website</a>
    </div>
    <div class="duplicate mt-6 flex flex-row items-center justify-center gap-x-4 text-gray-700">
      <div
        use:hoverTooltip={{
          text:
            'Duplicate the HuggingFace space to manage your own instance. ' +
            'You must be logged into HuggingFace for the duplicate modal to appear.'
        }}
      >
        <Button
          href={`https://huggingface.co/spaces/${huggingFaceSpaceId}?duplicate=true`}
          target="_blank"
          kind="tertiary">duplicate</Button
        >
      </div>
      <a
        class="-ml-2"
        use:hoverTooltip={{
          text:
            'See Lilac documentation on duplicating the HuggingFace space  ' +
            'so you can manage your own instance.'
        }}
        href="https://lilacml.com/huggingface/huggingface_spaces.html"><Help /></a
      >
    </div>
  </div>
  {#if $datasets.isFetching}
    <SkeletonText />
  {:else if hasTryDataset}
    <WelcomeBanner
      backgroundColorClass="bg-violet-300 hover:bg-violet-400"
      link={tryLink}
      title={`Browse the ${tryDataset.name} dataset`}
    >
      <p class="text-sm">
        Try the Lilac dataset viewer on the the pre-loaded <a
          target="_blank"
          href={tryDataset.originalLink}>{tryDataset.displayName}</a
        > dataset.
      </p>
    </WelcomeBanner>
  {/if}

  <WelcomeBanner
    backgroundColorClass="bg-violet-100 hover:bg-violet-200"
    link={'https://lilacml.com/blog/introducing-lilac.html'}
    title={`Read our Announcement Blog`}
  >
    <p class="text-sm">
      Read about how to get started and learn more about how to use Lilac for your data.
    </p>
  </WelcomeBanner>

  <WelcomeBanner
    backgroundColorClass="bg-violet-100 hover:bg-violet-200"
    link={'https://lilacml.com/'}
    title={`Documentation`}
  >
    <p class="text-sm">
      Find detailed documentation about how to install Lilac on your own machine, how to import your
      own data, and create your own concepts.
    </p>
  </WelcomeBanner>
</div>

<style lang="postcss">
  :global(.duplicate .bx--btn) {
    @apply min-h-0 px-4;
  }
</style>
