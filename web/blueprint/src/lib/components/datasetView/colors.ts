const SHOW_SCORE_THRESHOLD = 0.5;
const MIN_SCORE_BG_OPACITY = 0.1;
const MAX_SCORE_BG_OPACITY = 0.5;

// This color comes from tailwind bg-yellow-500.
export function colorFromOpacity(opacity: number) {
  return `rgba(234,179,8,${opacity})`;
}

export function colorFromScore(score: number) {
  let opacity = 0.0;
  // If the value has crossed the threshold, lerp the value between (min, max).
  if (score > SHOW_SCORE_THRESHOLD) {
    const normalizedScore = (score - SHOW_SCORE_THRESHOLD) / (1.0 - SHOW_SCORE_THRESHOLD);
    opacity =
      MIN_SCORE_BG_OPACITY + normalizedScore * (MAX_SCORE_BG_OPACITY - MIN_SCORE_BG_OPACITY);
  }
  return colorFromOpacity(opacity);
}
