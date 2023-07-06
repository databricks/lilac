<script lang="ts">
  import {formatValue, type ConceptMetrics} from '$lilac';
  import {scoreToColor, scoreToText} from './colors';
  export let metrics: ConceptMetrics;
</script>

<table>
  <tr>
    <td>Overall score</td><td class={scoreToColor[metrics.overall]}>
      {scoreToText[metrics.overall]}
    </td>
  </tr>
  <tr><td>F1</td><td>{formatValue(metrics.f1)}</td></tr>
  <tr><td>Recall</td><td>{formatValue(metrics.recall)}</td></tr>
  <tr><td>Precision</td><td>{formatValue(metrics.precision)}</td></tr>
  <tr><td>Area under ROC</td><td>{formatValue(metrics.roc_auc)}</td></tr>
</table>

<style lang="postcss">
  :global(.concept-score-pill .bx--tooltip__label) {
    @apply mr-1 inline-block h-full truncate;
    max-width: 5rem;
  }
  :global(.concept-score-pill .bx--tooltip__content) {
    @apply flex flex-col items-center;
  }
  table td {
    @apply px-2 py-1;
  }
</style>
